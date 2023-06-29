import csv
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator

import requests
from praw import Reddit
from praw.models import Submission

from account import Account
from download import Downloader


class Posts:
    post_path = Path("data/posts.json")
    fail_path = Path("data/failed.json")
    csv_path = Path("saved_posts.csv")

    downloader = Downloader()

    def __init__(self, account: "Account", debug: bool = False, _csv: bool = False, verbose: bool = False):
        self._posts = self.load_json(Posts.post_path)
        self._failed = {}

        self._reddit: Reddit = account.reddit
        self._imgur_keys = account.imgur_keys

        self._all_posts: Iterator[Submission] = self._get_posts()

        Posts.post_path.parent.mkdir(parents=True, exist_ok=True)

        self._added_count = 0
        self._failed_count = 0
        self._skipped = 0
        self._counter = 0

        self._debug = debug
        self._csv = _csv
        self._verbose = verbose
        Posts.downloader.verbose = verbose

        self.msg("Initialized!")

    def _get_posts(self) -> Iterator[Submission]:
        return self._reddit.info(fullnames=self.load_csv(Posts.csv_path)) \
            if self._csv \
            else self._reddit.user.me().saved(limit=None)

    def download_all(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            for post in self._all_posts:
                # self.download_post(post)
                pool.submit(self.download_post, post)

    def download_post(self, post: Submission):
        if not isinstance(post, Submission):
            return

        if post.id in self._posts:
            self._skipped += 1
            self.msg(f"Skipped post {post.id} from r/{self._posts[post.id]['sub']} - already in database")
            return

        entry = self.process_post(post)
        self.download_entry(entry, post.id)

    def process_post(self, praw_post: Submission) -> dict | None:
        if not isinstance(praw_post, Submission):
            return None

        post = self.post_to_dict(praw_post)
        post = self.fix_crosspost(post)
        entry = self.generate_entry(post)
        if entry["source"] == "" or entry["url"] == "" or entry["data"] == "[removed]" or entry["data"] == []:
            ps = self.get_pushshift_post(post.get("id"))
            entry = self.generate_entry(ps)

        return entry

    def generate_entry(self, post: dict) -> dict:
        url = post.get("url_overridden_by_dest", post.get("url", ""))

        url_preview = ""
        post_images = post.get("preview").get("images") or []
        if post_images:
            url_preview = post_images[0].get("source")("url") or ""

        entry = {
            "sub": str(post.get("subreddit", "")),
            "title": post.get("title", "").encode("ascii", "ignore").decode(),
            "author": str(post.get("author", "")) if post.get("author", "") is not None else "[deleted]",
            "date": post.get("created_utc", 0.0),
            "source": post.get("domain", ""),
            "url": url,
            "url_preview": url_preview,
            "data": "",
        }

        if post.get("is_self", False):
            entry["data"] = post.get("selftext", "")
        elif "reddit.com/gallery/" in url or "imgur.com/a/" in url:
            entry["data"] = self.process_gallery(url)

        if "imgur" in url and "/a/" not in url and Path(url).suffix == "":
            entry["url"] += ".png"

        return entry

    @staticmethod
    def get_pushshift_post(_id: str) -> dict:
        print(f"[Calling pushshift for post {_id}]")
        ps_api = "https://api.pushshift.io/reddit/search/submission"
        try:
            response = requests.get(ps_api, headers=Downloader.headers, params={"ids": _id}, timeout=30)
            response.raise_for_status()
            data = response.json().get("data")[0]
            return data
        except Exception:
            return {}

    def download_entry(self, entry: dict, _id: str):
        try:
            if not self._debug:
                Posts.downloader.download(entry, _id)
            self._added_count += 1
            self._posts[_id] = entry
            self.msg(f"Added post {_id} from r/{entry['sub']}")
        except Exception as e:
            self._failed_count += 1
            entry["error"] = str(e)
            self._failed[_id] = entry
            self.msg(f"Failed to add post {_id} from r/{entry['sub']}: {str(e)}")

        self._counter += 1
        if self._counter == 50:
            self.save_all(temp=True)
            self._counter = 0

    def post_to_dict(self, praw_post: Submission):
        print(praw_post.title)
        post = []
        try:
            # Verifies and loads PRAW object to deal with rare cases where submission object errors
            if hasattr(praw_post, "title") or True:
                post = vars(praw_post)
        except Exception:
            post = self.get_pushshift_post(praw_post.id)
        return post

    def fix_crosspost(self, post: dict) -> dict:
        crossposts = post.get("crosspost_parent_list")
        if crossposts and len(crossposts) > 0:
            praw_post = self._reddit.submission(id=crossposts[-1].get("id"))
            post = self.post_to_dict(praw_post)
        return post

    def process_gallery(self, link: str) -> list[str]:
        if self._verbose:
            print(f"Processing gallery at {link}")

        # Append Reddit gallery data to 'entry' so that it is not necessary to use PRAW again when downloading
        _id = link.strip("/").split("/")[-1]
        urls = []

        if "reddit.com/gallery/" in link:
            praw_post = self._reddit.submission(id=_id)
            post = self.post_to_dict(praw_post)

            if post.get("gallery_data", None) is None:
                try:
                    post = self.get_pushshift_post(_id)
                    if post.get("gallery_data", None) is None:
                        raise ValueError("Unable to extract album data via pushshift and praw")
                except Exception:
                    return urls

            # Get links to each image in Reddit gallery
            # Try block to account for possibility of some posts media data not containing "p", "u", etc. elements
            try:
                ord = [i["media_id"] for i in post["gallery_data"]["items"]]
                for key in ord:
                    img = post["media_metadata"][key]
                    if len(img["p"]) > 0:
                        url = img["p"][-1]["u"]
                    else:
                        url = img["s"]["u"]
                    url = url.split("?")[0].replace("preview", "i")
                    urls.append(url)
            except Exception:
                return urls

        elif "imgur.com/a/" in link:
            headers = dict(Downloader.headers)
            headers.update({
                "Authorization": f"Client-ID {self._imgur_keys[0]}"
            })

            try:
                response = requests.get(f"https://api.imgur.com/3/album/{_id}/images", headers=headers, timeout=30)
                response.raise_for_status()
                urls = [item["link"] for item in response.json()["data"]]

                if int(response.headers["x-ratelimit-clientremaining"]) < 1000:
                    self._imgur_keys.pop(0)
            except Exception as e:
                if self._verbose:
                    print(e)

        return urls

    def save_all(self, temp: bool = False):
        files = [(self._posts, Posts.post_path), (self._failed, Posts.fail_path)]

        self.msg(f"Saving items to JSON...")

        for (data, path) in files:
            self.save(data, path, temp=temp)

    def save(self, data: dict, path: Path, temp: bool = False):
        if self._debug:
            path = Path(str(path) + "_debug")

        path_temp = Path(str(path) + "_temp")

        if temp:
            path = path_temp
        else:
            if path_temp.is_file():
                path_temp.unlink()

        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def load_json(path: Path) -> list[Submission]:
        if path.is_file():
            with open(path) as f:
                posts = json.load(f)
        else:
            posts = {}

        path_temp = Path(str(path) + "_temp")

        if path_temp.is_file():
            with open(path_temp) as f:
                posts.update(json.load(f))

        return posts

    @staticmethod
    def load_csv(path: Path) -> list[str]:
        if not path.is_file():
            return []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            ids = [row[0] for row in reader]
            del ids[0]
        names = [_id if _id.startswith("t3_") else f"t3_{_id}" for _id in ids]
        return names

    def msg(self, msg):
        print(f"[T: {len(self._posts)}][A: {self._added_count}][F: {self._failed_count}][S: {self._skipped}] {msg}")

import json

from praw import Reddit


class Account:
    def __init__(self):
        with open("user.json") as f:
            data = json.load(f)

        self._imgur_keys: list[str] = data.get("imgur").get("client_id")
        self._reddit: Reddit = Reddit(
            user_agent="Geddit Saved Posts Backup Utility (by /u/aeluro1)",
            **data.get("reddit")
        )

        if not isinstance(self._imgur_keys, list):
            raise ValueError("Update user.json Imgur key format")

    @property
    def reddit(self):
        return self._reddit

    @property
    def imgur_keys(self):
        return self._imgur_keys

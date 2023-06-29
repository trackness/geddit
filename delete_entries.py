# This script will remove all items located in the data/_BIN folder from the saved registry.
# Use this when the program downloads an incorrect file, and a new update has rectified this behavior

from pathlib import Path
import json

_bin = Path("data/_BIN")
_bin.mkdir(parents=True, exist_ok=True)

posts = Path("data/posts.json")
with open(posts) as f:
    data = json.load(f)

posts.rename(posts.with_suffix(".old"))

count = 0
for item in _bin.iterdir():
    try:
        _id = item.name.split(" ")[0]
        if _id in data:
            data.pop(_id)
            print(f"{_id} removed")
            count += 1
    except:
        continue
print(f"{count} removed")

with open(posts, "w") as f:
    json.dump(data, f, indent=4)

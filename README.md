# Geddit

---
This program backs up a Reddit user's saved posts.

## Usage (Docker)
1. Clone the repository.
2. Run the following command to build an image from the Dockerfile.

    ```
    docker build --tag geddit .
    ```



## To Do
- [] Implement bloom filter to determine whether post is already saved
- [] Look into enabling streaming data in requests for handling larger downloads
- [] Implement comment downloading
- [] Implement progress bar with tqdm
- [] Store data in database rather than JSON
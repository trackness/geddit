import argparse

from account import Account
from posts import Posts


def main(args):
    account = Account()
    posts = Posts(account, args.debug, args.csv, args.verbose)
    posts.download_all()
    posts.save_all(temp=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Geddit")
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="to activate debug mode, where no files are downloaded",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="to process saved posts .csv file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="to print all log statements",
    )
    args = parser.parse_args()

    main(args)

"""Convert a Twitter archive export (``data/tweets.js``) to a CSV.

The archive file is JavaScript assigning a JSON array; the array is read
between the first ``[`` and the last ``]``. The output columns are the ones
consumed by ``hindsight.py`` (``created_at``, ``full_text``,
``retweet_count``, ``favorite_count``, ``lang``, ``id``).

Usage:

    python twitter_archive.py [path/to/tweets.js] [output-csv]

Defaults are ``data/tweets.js`` and ``twitter_archive.csv``. The archive file
itself is a personal export and is not committed to the repository.
"""

import json
import sys
from pathlib import Path

FIELDS = ("id", "created_at", "full_text", "retweet_count", "favorite_count", "lang")


def load_tweets(path):
    """Load the tweet array from a Twitter archive ``tweets.js`` file."""
    content = Path(path).read_text(encoding="utf-8")
    json_start = content.find('[')
    json_end = content.rfind(']') + 1
    return json.loads(content[json_start:json_end])


def tweets_to_rows(tweets):
    """Reduce archive entries to the columns used by the pipeline."""
    return [{field: tweet['tweet'][field] for field in FIELDS} for tweet in tweets]


def write_csv(rows, output_path):
    """Write the tweet rows as a CSV."""
    import pandas as pd

    pd.DataFrame(rows).to_csv(output_path, index=False)


def main(argv=None):
    """CLI entry point: ``twitter_archive.py [tweets.js] [output.csv]``."""
    argv = sys.argv[1:] if argv is None else argv
    input_path = argv[0] if len(argv) > 0 else "data/tweets.js"
    output_path = argv[1] if len(argv) > 1 else "twitter_archive.csv"

    try:
        tweets = load_tweets(input_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading {input_path}: {exc}")
        return 1

    print(tweets[0:10])
    write_csv(tweets_to_rows(tweets), output_path)
    print("Twitter archive has been successfully converted to CSV.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

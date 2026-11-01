"""Build a prompt→completion sentence-pair CSV from a text file.

Reads a plain-text file (one paragraph per line) and writes a CSV with
``prompt,completion`` columns pairing each sentence with its successor, using
NLTK's sentence tokenizer.

Usage:

    python text_process.py [input-file] [output-csv]

Defaults are the historical ``ceresonepage`` input and ``ceresonepage.csv``
output. NLTK sentence tokenization needs its ``punkt`` data; if it is missing,
run ``python -m nltk.downloader punkt`` first.
"""

import csv
import sys


def sentence_pairs(text):
    """Pair each sentence of ``text`` with the sentence that follows it."""
    from nltk import tokenize

    sentences = []
    for paragraph in text.splitlines():
        sentences += tokenize.sent_tokenize(paragraph)

    pairs = []
    for i in range(len(sentences) - 1):
        pairs.append({"prompt": sentences[i], "completion": sentences[i + 1]})
    return pairs


def write_pairs(pairs, output_path):
    """Write sentence pairs as a two-column CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['prompt', 'completion'])
        for pair in pairs:
            writer.writerow([pair["prompt"], pair["completion"]])


def main(argv=None):
    """CLI entry point: ``text_process.py [input-file] [output-csv]``."""
    argv = sys.argv[1:] if argv is None else argv
    input_path = argv[0] if len(argv) > 0 else "ceresonepage"
    output_path = argv[1] if len(argv) > 1 else "ceresonepage.csv"

    with open(input_path, encoding='utf-8') as handle:
        text = handle.read()

    write_pairs(sentence_pairs(text), output_path)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Parse a URL or PDF into FourThought thought types via OpenRouter.

Usage:

    python parse_fourthought.py http://example.com      # URL (headless Selenium)
    python parse_fourthought.py /path/to/paper.pdf      # PDF (pypdf)

The text is cleaned, split into chunks, and sent to the ``thought_type``
OpenRouter chat model with a system prompt describing the FourThought
dialectic and the exact output format ``THOUGHT_TEXT, THOUGHT_TYPE``. Matches
are printed as thought text and type separately.

Model calls go through :mod:`iris_llm` (``OPENROUTER_API_KEY``, falling back
to ``OPENAI_API_KEY``). Importing this module has no side effects; the CLI
entry point is :func:`main`.
"""

import re
import sys

import iris_llm

# One parsed thought per line: "<thought text>, <TYPE>"
PATTERN = r"^(.*),\s*(PREDICTION|REFLECTION|STATEMENT|QUESTION)$"

# Fine-tuned davinci models are retired; the slots map to catalog-verified
# OpenRouter chat models (checked by scripts/check_openrouter_models.py).
models = {
    "semantic": "openai/gpt-4o-mini",
    "davinci": "openai/gpt-4o-mini",
    "thought_type": "openai/gpt-4o-mini",
}

# Maximum length of each text chunk sent to the model.
chunk_length = 3000

SYSTEM_PROMPT = (
    "You are a kind and prophetic assistant that takes in noisy text scraped "
    "from the internet parses it into the FourThought Dialectic: Predictions, "
    "Statements, Reflections and Questions"
)

EXPLANATION = (
    "The fourThought dialectic is about the tensing of the language and the certainty behind it. It has four thought types: predictions, statements, reflections and questions. Predictions are claims about the future, reflections are claims about the past, statements are claims about the present. Questions are not declarations of truth. They are the opposite, they query the world based on uncertainty.\n\n"
    "I want you to read this text and break it into predictions, reflections, statements and questions.\n\n"
    "Print each thought like this THOUGHT_TEXT, THOUGHT_TYPE. \n\n"
    "The world will continue on well past 2042, PREDICTION\n"
    "In the early 1900's the Spanish flu became a pandemic, REFLECTION\n"
    "The world is a vampire, STATEMENT\n"
    "The future is bright and prosperous, PREDICTION\n"
    "This will require new tools PREDICTION\n"
    "Where did I leave my keys? QUESTION?\n\n"
    "The text you are receiving is scraped from the internet. It may be noisy and contain non-standard capitalization. Strip white space and recase the claims to be readable by humans. Follow the format above in printing with one line between each discrete thought.\n\n"
    "You will be reading text from the internet and parsing it into four thought types. Reflections are about the past. Statements are about now. Predictions are about the future. Predictions can't be verified until time passes. Memories can be verified by referencing a record. If a thought is a reflection we should be able to check the record to see if it matches. Statements are about now and can be verified through a democratic process of asking the community. Predictions can not be verified immediately. Time must pass for predictions to be verified."
)

ASSISTANT_ACK = (
    "Okay I will print one thought per line with the thought type at the end. "
    "Thoughts about the future will be labeled as PREDICTION and thoughts "
    "about the past will be labeled as REFLECTION. All other thoughts will be "
    "labeled STATEMENT or QUESTION"
)


def extract_text_from_url(url):
    """Fetch a page's visible text with headless Selenium + BeautifulSoup."""
    # Imported here so the module imports without a browser stack installed.
    from selenium import webdriver
    from bs4 import BeautifulSoup

    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('disable-gpu')
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        html_content = driver.page_source
    finally:
        driver.quit()
    return BeautifulSoup(html_content, 'html.parser').get_text()


def extract_text_from_pdf(path):
    """Extract the text of every page of a PDF with pypdf."""
    from pypdf import PdfReader

    with open(path, 'rb') as f:
        reader = PdfReader(f)
        return ''.join(page.extract_text() or '' for page in reader.pages)


def clean_text(text):
    """Apply the pipeline's cleaning: single-line text, recased sentences."""
    text = text.replace('\n', ' ')
    sentences = text.split('. ')
    formatted_sentences = []
    for sentence in sentences:
        formatted_sentence = sentence.capitalize()
        formatted_sentence = formatted_sentence[0] + formatted_sentence[1:].lower()
        formatted_sentences.append(formatted_sentence)
    return '. '.join(formatted_sentences)


def chunk_text(text, max_chunk_length=chunk_length):
    """Split text into chunks of at most ``max_chunk_length`` characters."""
    return [text[i:i + max_chunk_length] for i in range(0, len(text), max_chunk_length)]


def parse_thoughts(text, model=None):
    """Send the text to the model chunk by chunk; return the printed lines.

    The conversation grows with each chunk and only the last four messages are
    replayed per request, matching the original pipeline behavior.
    """
    if model is None:
        model = models["thought_type"]

    claims = []
    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation.append({"role": "user", "content": EXPLANATION})

    for text_chunk in chunk_text(text):
        text_prompt = "Here is the current chunk of text \n" + text_chunk + "\n"
        conversation.append({"role": "user", "content": text_prompt})

        truncated_convo = [
            {"role": "user", "content": EXPLANATION},
            {"role": "assistant", "content": ASSISTANT_ACK},
        ]
        truncated_convo += conversation[-4:]

        response = iris_llm.chat_completion(truncated_convo, model=model)
        for choice in response.choices:
            assistant_message = choice.message.content
            conversation.append({"role": "assistant", "content": assistant_message})
            claims += [c.strip() for c in assistant_message.split("\n") if c.strip()]

    return claims


def classify_claim(claim):
    """Return ``(thought, type)`` for a model line, or ``None`` if malformed."""
    match = re.match(PATTERN, claim)
    if not match:
        return None
    return match.group(1), match.group(2).upper()


def main(argv=None):
    """CLI entry point: ``parse_fourthought.py <url-or-pdf>``."""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__.strip())
        return 2

    input_file = argv[0]
    try:
        if input_file.startswith('http'):
            text = extract_text_from_url(input_file)
        elif input_file.endswith('.pdf'):
            text = extract_text_from_pdf(input_file)
        else:
            print("Invalid input file format. Please provide a URL or a PDF file.")
            return 1
    except Exception as exc:
        print(f"Failed to read input file: {exc}")
        return 1

    for claim in parse_thoughts(clean_text(text)):
        parsed = classify_claim(claim)
        if parsed:
            thought, thought_type = parsed
            print(thought)
            print("\n")
            print(thought_type)
            print("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

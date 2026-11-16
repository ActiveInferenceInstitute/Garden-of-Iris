"""Canonical OpenRouter model client for the Garden-of-Iris scripts.

Every model call in this repository goes through this module. It builds the
current OpenAI SDK client (``openai >= 1.0``) against OpenRouter's
OpenAI-compatible chat-completions endpoint, resolves the API key, and sets
the OpenRouter attribution headers.

Two helpers cover the call styles used here:

- :func:`chat` — send a chat conversation, return the first choice's text.
- :func:`complete` — send a single prompt as one user message (the retired
  legacy ``/completions`` call style, expressed in the current chat API) and
  return the first choice's text.

:func:`chat_completion` returns the raw SDK response for the one call site
that reads every choice.

Credentials come from ``OPENROUTER_API_KEY``, falling back to
``OPENAI_API_KEY``. Set them in the environment (see ``.env.example``); never
commit a key.
"""

import os
import threading

import openai

# Re-exported so scripts can retry without importing the SDK themselves.
from openai import APITimeoutError, RateLimitError

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_REFERER = "https://github.com/ActiveInferenceInstitute/Garden-of-Iris"
OPENROUTER_TITLE = "Garden-of-Iris"

_client = None
_client_lock = threading.Lock()


class ModelOutputError(ValueError):
    """The provider returned no usable text; no replacement text is invented."""


def _choices(response):
    choices = getattr(response, "choices", None)
    if not isinstance(choices, (list, tuple)) or not choices:
        raise ModelOutputError("Model response contains no text choices")
    return choices


def _choice_text(choice):
    message = getattr(choice, "message", None)
    if getattr(message, "refusal", None):
        raise ModelOutputError("Model declined to provide text")
    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise ModelOutputError("Model choice contains no usable text")
    return content.strip()


def response_texts(response):
    """Read every requested choice through the canonical text/error contract."""
    return [_choice_text(choice) for choice in _choices(response)]


def get_api_key():
    """Return the OpenRouter API key, falling back to ``OPENAI_API_KEY``."""
    return os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")


def get_client():
    """Return the shared OpenRouter client, creating it on first use."""
    global _client
    with _client_lock:
        if _client is None:
            _client = openai.OpenAI(
                api_key=get_api_key(),
                base_url=OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": OPENROUTER_REFERER,
                    "X-OpenRouter-Title": OPENROUTER_TITLE,
                },
            )
    return _client


def chat_completion(messages, model, **params):
    """Send a chat conversation and return the raw SDK response."""
    return get_client().chat.completions.create(
        model=model, messages=messages, **params
    )


def chat(messages, model, **params):
    """Send a chat conversation and return the first choice's text."""
    response = chat_completion(messages, model, **params)
    return _choice_text(_choices(response)[0])


def complete(prompt, model, **params):
    """Send one prompt as a single user message and return the response text."""
    if isinstance(prompt, list):  # the legacy API also accepted prompt arrays
        prompt = "\n".join(prompt)
    return chat([{"role": "user", "content": prompt}], model, **params)

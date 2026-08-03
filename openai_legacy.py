"""Legacy OpenAI API compatibility shim, routed through OpenRouter.

The scripts in this repository were written against the pre-1.0 OpenAI Python
package: module-level ``openai.api_key``, ``openai.Completion.create(...)``,
``openai.ChatCompletion.create(...)``, and the ``openai.error.*`` exception
namespace.

This module patches those legacy names onto the installed ``openai`` package
(``openai >= 1.0``) and routes every call through **OpenRouter**
(``https://openrouter.ai/api/v1``), which serves an OpenAI-compatible chat
completions API. Because OpenRouter does not expose the legacy ``/completions``
endpoint, ``openai.Completion.create(prompt=...)`` is emulated by translating
the prompt into a chat message; responses are wrapped so both legacy access
styles work (``response.choices[0].text`` and ``response['choices'][0]['text']``).

Credentials come from the ``OPENROUTER_API_KEY`` environment variable, with a
fallback to ``OPENAI_API_KEY``. OpenRouter attribution headers
(``HTTP-Referer`` / ``X-OpenRouter-Title``) are set from this repository's
public URL.

Usage:

    import openai
    import openai_legacy
    openai_legacy.patch()

If an ``openai`` package older than 1.0 is installed (which already exposes
``Completion`` and ``ChatCompletion``), ``patch()`` is a no-op.
"""

import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_REFERER = "https://github.com/ActiveInferenceInstitute/Garden-of-Iris"
OPENROUTER_TITLE = "Garden-of-Iris"


class _AttrDict(dict):
    """A dict that also supports attribute access, mirroring how the legacy
    openai package exposed response objects (both styles were used by the
    scripts: ``response['choices'][0]['text']`` and
    ``response.choices[0].text``)."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


def _wrap(obj):
    """Recursively convert an openai response object into ``_AttrDict`` trees."""
    if isinstance(obj, list):
        return [_wrap(x) for x in obj]
    if hasattr(obj, "model_dump"):  # pydantic v2 (openai >= 1.0)
        return _wrap(obj.model_dump())
    if hasattr(obj, "dict"):  # pydantic v1
        return _wrap(obj.dict())
    if isinstance(obj, dict):
        return _AttrDict({k: _wrap(v) for k, v in obj.items()})
    if hasattr(obj, "__dict__"):  # namespace-style objects (e.g. SimpleNamespace)
        return _wrap(vars(obj))
    return obj


def _to_legacy_completion(chat_response):
    """Adapt a chat-completions response to the legacy completion shape.

    OpenRouter (and the openai 1.x client) return chat responses whose text
    lives at ``choices[].message.content``; the scripts read
    ``choices[].text``. Expose ``text`` as an alias on each choice.
    """
    response = _wrap(chat_response)
    for choice in response.get("choices", []):
        if "message" in choice and "text" not in choice:
            choice["text"] = choice["message"]["content"]
    return response


def patch(openai=None, api_key_env="OPENROUTER_API_KEY", base_url=OPENROUTER_BASE_URL,
          extra_headers=None):
    """Install legacy API shims on the ``openai`` module (idempotent).

    Args:
        openai: The ``openai`` module to patch; imported if not given.
        api_key_env: Primary environment variable for the API key.
            ``OPENAI_API_KEY`` is used as a fallback.
        base_url: API base URL (OpenRouter by default).
        extra_headers: Additional default headers for the client.

    Returns:
        The patched ``openai`` module.
    """
    if openai is None:
        import openai

    # Pre-1.0 packages already provide the legacy API; nothing to do.
    if hasattr(openai, "Completion") and hasattr(openai, "ChatCompletion"):
        return openai

    _client = None

    def _get_client():
        nonlocal _client
        if _client is None:
            headers = {"HTTP-Referer": OPENROUTER_REFERER,
                       "X-OpenRouter-Title": OPENROUTER_TITLE}
            if extra_headers:
                headers.update(extra_headers)
            api_key = os.getenv(api_key_env) or os.getenv("OPENAI_API_KEY")
            _client = openai.OpenAI(api_key=api_key, base_url=base_url,
                                    default_headers=headers)
        return _client

    class Completion:
        @staticmethod
        def create(*args, **kwargs):
            # Legacy completions are emulated as chat completions, because
            # OpenRouter does not serve the legacy /completions endpoint.
            prompt = kwargs.pop("prompt", "")
            if isinstance(prompt, list):  # pre-1.0 allowed prompt arrays
                prompt = "\n".join(prompt)
            messages = [{"role": "user", "content": prompt}]
            return _to_legacy_completion(
                _get_client().chat.completions.create(messages=messages, **kwargs))

    class ChatCompletion:
        @staticmethod
        def create(*args, **kwargs):
            return _to_legacy_completion(_get_client().chat.completions.create(**kwargs))

    openai.Completion = Completion
    openai.ChatCompletion = ChatCompletion

    # Legacy exception namespace: map pre-1.0 names onto the 1.x exceptions.
    if not hasattr(openai, "error"):
        openai.error = type("error", (), {})
    for legacy_name, modern_name in (
        ("RateLimitError", "RateLimitError"),
        ("Timeout", "APITimeoutError"),
        ("APIError", "APIError"),
        ("AuthenticationError", "AuthenticationError"),
        ("PermissionError", "PermissionError"),
        ("InvalidRequestError", "BadRequestError"),
    ):
        if hasattr(openai, modern_name):
            setattr(openai.error, legacy_name, getattr(openai, modern_name))

    return openai

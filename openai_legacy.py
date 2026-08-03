"""Legacy OpenAI API compatibility shim for openai >= 1.0.

The scripts in this repository were written against the pre-1.0 OpenAI Python
package: module-level ``openai.api_key``, ``openai.Completion.create(...)``,
``openai.ChatCompletion.create(...)``, and the ``openai.error.*`` exception
namespace.

The 1.x package replaced these with a client-based API
(``openai.OpenAI().completions.create(...)``). This module patches the legacy
names onto the installed ``openai`` package so the scripts run against
``openai >= 1.0`` without rewriting every call site.

Usage:

    import openai
    import openai_legacy
    openai_legacy.patch()

If an ``openai`` package older than 1.0 is installed (which already exposes
``Completion`` and ``ChatCompletion``), ``patch()`` is a no-op.
"""

import os


def patch(openai=None, api_key_env="OPENAI_API_KEY"):
    """Install legacy API shims on the ``openai`` module (idempotent).

    Args:
        openai: The ``openai`` module to patch; imported if not given.
        api_key_env: Environment variable read for the API key. The 1.x
            client also falls back to ``OPENAI_API_KEY`` on its own when the
            key is ``None``.

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
            _client = openai.OpenAI(api_key=os.getenv(api_key_env))
        return _client

    class Completion:
        @staticmethod
        def create(*args, **kwargs):
            return _get_client().completions.create(*args, **kwargs)

    class ChatCompletion:
        @staticmethod
        def create(*args, **kwargs):
            return _get_client().chat.completions.create(*args, **kwargs)

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

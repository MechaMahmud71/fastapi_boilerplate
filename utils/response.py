"""Helpers for the standard API envelope.

Successful responses:

    {"success": true, "data": object | null, "message": str | null}

Error responses:

    {"success": false, "data": null, "errors": [str, ...], "message": str}

Controllers/services just return their payload; the ResponseInterceptor wraps
it. Error bodies are built by the handlers in modules/common/middlewares.
"""
from typing import Any, List, Optional


def envelope(data: Any = None, message: Optional[str] = None) -> dict:
    """Body of a successful response. Key order is stable."""
    return {"success": True, "data": data, "message": message}


def error_envelope(
    message: str,
    errors: Optional[List[str]] = None,
    data: Any = None,
) -> dict:
    """Body of a failed response.

    ``errors`` is always a list of strings: validation failures supply one entry
    per field, everything else falls back to a single-element list holding
    ``message``.
    """
    return {
        "success": False,
        "data": data,
        "errors": errors if errors is not None else [message],
        "message": message,
    }

"""Helper functions for cloud components."""
from __future__ import annotations

from typing import Any

from aiohttp import payload, web


def aiohttp_serialize_response(response: web.Response) -> dict[str, Any]:
    """Serialize an aiohttp response to a dictionary."""
    if (body := response.body) is None:
        body_decoded = None
    elif isinstance(body, payload.StringPayload):
        # pylint: disable=protected-access
        body_decoded = body._value.decode(body.encoding)
    elif isinstance(body, bytes):
        body_decoded = body.decode(response.charset or "utf-8")
    else:
        raise ValueError("Unknown payload encoding")

    return {
        "status": response.status,
        "body": body_decoded,
        "headers": dict(response.headers),
    }

"""Helper functions for cloud components."""
from typing import Any, Dict

from aiohttp import payload, web


def aiohttp_serialize_response(response: web.Response) -> Dict[str, Any]:
    """Serialize an aiohttp response to a dictionary."""
    body = response.body

    if body is None:
        pass
    elif isinstance(body, payload.StringPayload):
        # pylint: disable=protected-access
        body = body._value.decode(body.encoding)
    elif isinstance(body, bytes):
        body = body.decode(response.charset or "utf-8")
    else:
        raise ValueError("Unknown payload encoding")

    return {"status": response.status, "body": body, "headers": dict(response.headers)}

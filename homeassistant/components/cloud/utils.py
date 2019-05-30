"""Helper functions for cloud components."""
from typing import Any, Dict

from aiohttp import web


def aiohttp_serialize_response(response: web.Response) -> Dict[str, Any]:
    """Serialize an aiohttp response to a dictionary."""
    return {
        'status': response.status,
        'body': response.text,
        'headers': dict(response.headers),
    }

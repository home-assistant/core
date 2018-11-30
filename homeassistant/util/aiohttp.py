"""Utilities to help with aiohttp."""
import json
from urllib.parse import parse_qsl
from typing import Any, Dict, Optional

from aiohttp import web
from multidict import CIMultiDict, MultiDict


class MockRequest:
    """Mock an aiohttp request."""

    def __init__(self, content: bytes, method: str = 'GET',
                 status: int = 200, headers: Optional[Dict[str, str]] = None,
                 query_string: Optional[str] = None, url: str = '') -> None:
        """Initialize a request."""
        self.method = method
        self.url = url
        self.status = status
        self.headers = CIMultiDict(headers or {})  # type: CIMultiDict[str]
        self.query_string = query_string or ''
        self._content = content

    @property
    def query(self) -> 'MultiDict[str]':
        """Return a dictionary with the query variables."""
        return MultiDict(parse_qsl(self.query_string, keep_blank_values=True))

    @property
    def _text(self) -> str:
        """Return the body as text."""
        return self._content.decode('utf-8')

    async def json(self) -> Any:
        """Return the body as JSON."""
        return json.loads(self._text)

    async def post(self) -> 'MultiDict[str]':
        """Return POST parameters."""
        return MultiDict(parse_qsl(self._text, keep_blank_values=True))

    async def text(self) -> str:
        """Return the body as text."""
        return self._text


def serialize_response(response: web.Response) -> Dict[str, Any]:
    """Serialize an aiohttp response to a dictionary."""
    return {
        'status': response.status,
        'body': response.body,
        'headers': dict(response.headers),
    }

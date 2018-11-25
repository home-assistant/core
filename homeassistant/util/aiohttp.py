"""Utilities to help with aiohttp."""
import json
from urllib.parse import parse_qsl

from multidict import CIMultiDict, MultiDict


class MockRequest:
    """Mock an aiohttp request."""

    def __init__(self, content, method='GET', status=200, headers=None,
                 query_string=None, url=''):
        """Initialize a request."""
        self.method = method
        self.url = url
        self.status = status
        self.headers = CIMultiDict(headers or {})
        self.query_string = query_string
        self._content = content

    @property
    def query(self):
        """Return a dictionary with the query variables."""
        return MultiDict(parse_qsl(self.query_string, keep_blank_values=True))

    @property
    def _text(self):
        """Return the body as text."""
        return self._content.decode('utf-8')

    async def json(self):
        """Return the body as JSON."""
        return json.loads(self._text)

    async def post(self):
        """Return POST parameters."""
        return MultiDict(parse_qsl(self._text, keep_blank_values=True))

    async def text(self):
        """Return the body as text."""
        return self._text

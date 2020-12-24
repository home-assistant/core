"""Utilities to help with aiohttp."""
import io
import json
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl

from multidict import CIMultiDict, MultiDict

from homeassistant.const import HTTP_OK


class MockStreamReader:
    """Small mock to imitate stream reader."""

    def __init__(self, content: bytes) -> None:
        """Initialize mock stream reader."""
        self._content = io.BytesIO(content)

    async def read(self, byte_count: int = -1) -> bytes:
        """Read bytes."""
        if byte_count == -1:
            return self._content.read()
        return self._content.read(byte_count)


class MockRequest:
    """Mock an aiohttp request."""

    mock_source: Optional[str] = None

    def __init__(
        self,
        content: bytes,
        mock_source: str,
        method: str = "GET",
        status: int = HTTP_OK,
        headers: Optional[Dict[str, str]] = None,
        query_string: Optional[str] = None,
        url: str = "",
    ) -> None:
        """Initialize a request."""
        self.method = method
        self.url = url
        self.status = status
        self.headers: CIMultiDict[str] = CIMultiDict(headers or {})
        self.query_string = query_string or ""
        self._content = content
        self.mock_source = mock_source

    @property
    def query(self) -> "MultiDict[str]":
        """Return a dictionary with the query variables."""
        return MultiDict(parse_qsl(self.query_string, keep_blank_values=True))

    @property
    def _text(self) -> str:
        """Return the body as text."""
        return self._content.decode("utf-8")

    @property
    def content(self) -> MockStreamReader:
        """Return the body as text."""
        return MockStreamReader(self._content)

    async def json(self) -> Any:
        """Return the body as JSON."""
        return json.loads(self._text)

    async def post(self) -> "MultiDict[str]":
        """Return POST parameters."""
        return MultiDict(parse_qsl(self._text, keep_blank_values=True))

    async def text(self) -> str:
        """Return the body as text."""
        return self._text

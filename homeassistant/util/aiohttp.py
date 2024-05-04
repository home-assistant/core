"""Utilities to help with aiohttp."""

from __future__ import annotations

from http import HTTPStatus
import io
from typing import Any
from urllib.parse import parse_qsl

from aiohttp import payload, web
from aiohttp.typedefs import JSONDecoder
from multidict import CIMultiDict, MultiDict

from .json import json_loads


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

    mock_source: str | None = None

    def __init__(
        self,
        content: bytes,
        mock_source: str,
        method: str = "GET",
        status: int = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
        query_string: str | None = None,
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
    def query(self) -> MultiDict[str]:
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

    @property
    def body_exists(self) -> bool:
        """Return True if request has HTTP BODY, False otherwise."""
        return bool(self._text)

    async def json(self, loads: JSONDecoder = json_loads) -> Any:
        """Return the body as JSON."""
        return loads(self._text)

    async def post(self) -> MultiDict[str]:
        """Return POST parameters."""
        return MultiDict(parse_qsl(self._text, keep_blank_values=True))

    async def text(self) -> str:
        """Return the body as text."""
        return self._text


def serialize_response(response: web.Response) -> dict[str, Any]:
    """Serialize an aiohttp response to a dictionary."""
    if (body := response.body) is None:
        body_decoded = None
    elif isinstance(body, payload.StringPayload):
        # pylint: disable-next=protected-access
        body_decoded = body._value.decode(body.encoding)
    elif isinstance(body, bytes):
        body_decoded = body.decode(response.charset or "utf-8")
    else:
        raise TypeError("Unknown payload encoding")

    return {
        "status": response.status,
        "body": body_decoded,
        "headers": dict(response.headers),
    }

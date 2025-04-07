"""Aiohttp test utils."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
import re
from types import TracebackType
from typing import Any
from unittest import mock
from urllib.parse import parse_qs

from aiohttp import ClientSession
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientError,
    ClientResponseError,
)
from aiohttp.streams import StreamReader
from multidict import CIMultiDict
from yarl import URL

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads

RETYPE = type(re.compile(""))


def mock_stream(data):
    """Mock a stream with data."""
    protocol = mock.Mock(_reading_paused=False)
    stream = StreamReader(protocol, limit=2**16)
    stream.feed_data(data)
    stream.feed_eof()
    return stream


class AiohttpClientMocker:
    """Mock Aiohttp client requests."""

    def __init__(self) -> None:
        """Initialize the request mocker."""
        self._mocks = []
        self._cookies = {}
        self.mock_calls = []

    def request(
        self,
        method,
        url,
        *,
        auth=None,
        status=HTTPStatus.OK,
        text=None,
        data=None,
        content=None,
        json=None,
        params=None,
        headers=None,
        exc=None,
        cookies=None,
        side_effect=None,
        closing=None,
    ):
        """Mock a request."""
        if not isinstance(url, RETYPE):
            url = URL(url)
        if params:
            url = url.with_query(params)

        self._mocks.append(
            AiohttpClientMockResponse(
                method=method,
                url=url,
                status=status,
                response=content,
                json=json,
                text=text,
                cookies=cookies,
                exc=exc,
                headers=headers,
                side_effect=side_effect,
                closing=closing,
            )
        )

    def get(self, *args, **kwargs):
        """Register a mock get request."""
        self.request("get", *args, **kwargs)

    def put(self, *args, **kwargs):
        """Register a mock put request."""
        self.request("put", *args, **kwargs)

    def post(self, *args, **kwargs):
        """Register a mock post request."""
        self.request("post", *args, **kwargs)

    def delete(self, *args, **kwargs):
        """Register a mock delete request."""
        self.request("delete", *args, **kwargs)

    def options(self, *args, **kwargs):
        """Register a mock options request."""
        self.request("options", *args, **kwargs)

    def patch(self, *args, **kwargs):
        """Register a mock patch request."""
        self.request("patch", *args, **kwargs)

    @property
    def call_count(self):
        """Return the number of requests made."""
        return len(self.mock_calls)

    def clear_requests(self):
        """Reset mock calls."""
        self._mocks.clear()
        self._cookies.clear()
        self.mock_calls.clear()

    def create_session(self, loop):
        """Create a ClientSession that is bound to this mocker."""
        session = ClientSession(loop=loop, json_serialize=json_dumps)
        # Setting directly on `session` will raise deprecation warning
        object.__setattr__(session, "_request", self.match_request)
        return session

    async def match_request(
        self,
        method,
        url,
        *,
        data=None,
        auth=None,
        params=None,
        headers=None,
        allow_redirects=None,
        timeout=None,
        json=None,
        cookies=None,
        **kwargs,
    ):
        """Match a request against pre-registered requests."""
        data = data or json
        url = URL(url)
        if params:
            url = url.with_query(params)

        for response in self._mocks:
            if response.match_request(method, url, params):
                self.mock_calls.append((method, url, data, headers))
                if response.side_effect:
                    response = await response.side_effect(method, url, data)
                if response.exc:
                    raise response.exc
                return response

        raise AssertionError(f"No mock registered for {method.upper()} {url} {params}")


class AiohttpClientMockResponse:
    """Mock Aiohttp client response."""

    def __init__(
        self,
        method,
        url: URL,
        status=HTTPStatus.OK,
        response=None,
        json=None,
        text=None,
        cookies=None,
        exc=None,
        headers=None,
        side_effect=None,
        closing=None,
    ) -> None:
        """Initialize a fake response."""
        if json is not None:
            text = json_dumps(json)
        if text is not None:
            response = text.encode("utf-8")
        if response is None:
            response = b""

        self.charset = "utf-8"
        self.method = method
        self._url = url
        self.status = status
        self._response = response
        self.exc = exc
        self.side_effect = side_effect
        self.closing = closing
        self._headers = CIMultiDict(headers or {})
        self._cookies = {}

        if cookies:
            for name, data in cookies.items():
                cookie = mock.MagicMock()
                cookie.value = data
                self._cookies[name] = cookie

    def match_request(self, method, url, params=None):
        """Test if response answers request."""
        if method.lower() != self.method.lower():
            return False

        # regular expression matching
        if isinstance(self._url, RETYPE):
            return self._url.search(str(url)) is not None

        if (
            self._url.scheme != url.scheme
            or self._url.host != url.host
            or self._url.path != url.path
        ):
            return False

        # Ensure all query components in matcher are present in the request
        request_qs = parse_qs(url.query_string)
        matcher_qs = parse_qs(self._url.query_string)
        for key, vals in matcher_qs.items():
            for val in vals:
                try:
                    request_qs.get(key, []).remove(val)
                except ValueError:
                    return False

        return True

    @property
    def headers(self):
        """Return content_type."""
        return self._headers

    @property
    def cookies(self):
        """Return dict of cookies."""
        return self._cookies

    @property
    def url(self):
        """Return yarl of URL."""
        return self._url

    @property
    def content_type(self):
        """Return yarl of URL."""
        return self._headers.get("content-type")

    @property
    def content(self):
        """Return content."""
        return mock_stream(self.response)

    async def read(self):
        """Return mock response."""
        return self.response

    async def text(self, encoding="utf-8", errors="strict"):
        """Return mock response as a string."""
        return self.response.decode(encoding, errors=errors)

    async def json(self, encoding="utf-8", content_type=None, loads=json_loads):
        """Return mock response as a json."""
        return loads(self.response.decode(encoding))

    def release(self):
        """Mock release."""

    def raise_for_status(self):
        """Raise error if status is 400 or higher."""
        if self.status >= 400:
            request_info = mock.Mock(real_url="http://example.com")
            raise ClientResponseError(
                request_info=request_info,
                history=None,
                status=self.status,
                headers=self.headers,
            )

    def close(self):
        """Mock close."""

    async def wait_for_close(self):
        """Wait until all requests are done.

        Do nothing as we are mocking.
        """

    @property
    def response(self):
        """Property method to expose the response to other read methods."""
        if self.closing:
            raise ClientConnectionError("Connection closed")
        return self._response

    async def __aenter__(self):
        """Enter the context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager."""


@contextmanager
def mock_aiohttp_client() -> Iterator[AiohttpClientMocker]:
    """Context manager to mock aiohttp client."""
    mocker = AiohttpClientMocker()

    def create_session(hass: HomeAssistant, *args: Any, **kwargs: Any) -> ClientSession:
        session = mocker.create_session(hass.loop)

        async def close_session(event):
            """Close session."""
            await session.close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, close_session)

        return session

    with mock.patch(
        "homeassistant.helpers.aiohttp_client._async_create_clientsession",
        side_effect=create_session,
    ):
        yield mocker


class MockLongPollSideEffect:
    """Imitate a long_poll request.

    It should be created and used as a side effect for a GET/PUT/etc. request.
    Once created, actual responses are queued with queue_response
    If queue is empty, will await until done.
    """

    def __init__(self) -> None:
        """Initialize the queue."""
        self.semaphore = asyncio.Semaphore(0)
        self.response_list = []
        self.stopping = False

    async def __call__(self, method, url, data):
        """Fetch the next response from the queue or wait until the queue has items."""
        if self.stopping:
            raise ClientError
        await self.semaphore.acquire()
        kwargs = self.response_list.pop(0)
        return AiohttpClientMockResponse(method=method, url=url, **kwargs)

    def queue_response(self, **kwargs):
        """Add a response to the long_poll queue."""
        self.response_list.append(kwargs)
        self.semaphore.release()

    def stop(self):
        """Stop the current request and future ones.

        This avoids an exception if there is someone waiting when exiting test.
        """
        self.stopping = True
        self.queue_response(exc=ClientError())

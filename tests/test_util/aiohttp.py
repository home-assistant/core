"""Aiohttp test utils."""
import asyncio
from contextlib import contextmanager
import functools
import json as _json
from unittest import mock


class AiohttpClientMocker:
    """Mock Aiohttp client requests."""

    def __init__(self):
        """Initialize the request mocker."""
        self._mocks = []
        self.mock_calls = []

    def request(self, method, url, *,
                status=200,
                text=None,
                content=None,
                json=None):
        """Mock a request."""
        if json:
            text = _json.dumps(json)
        if text:
            content = text.encode('utf-8')
        if content is None:
            content = b''

        self._mocks.append(AiohttpClientMockResponse(
            method, url, status, content))

    def get(self, *args, **kwargs):
        """Register a mock get request."""
        self.request('get', *args, **kwargs)

    def put(self, *args, **kwargs):
        """Register a mock put request."""
        self.request('put', *args, **kwargs)

    def post(self, *args, **kwargs):
        """Register a mock post request."""
        self.request('post', *args, **kwargs)

    def delete(self, *args, **kwargs):
        """Register a mock delete request."""
        self.request('delete', *args, **kwargs)

    def options(self, *args, **kwargs):
        """Register a mock options request."""
        self.request('options', *args, **kwargs)

    @property
    def call_count(self):
        """Number of requests made."""
        return len(self.mock_calls)

    @asyncio.coroutine
    def match_request(self, method, url):
        """Match a request against pre-registered requests."""
        for response in self._mocks:
            if response.match_request(method, url):
                self.mock_calls.append((method, url))
                return response

        assert False, "No mock registered for {} {}".format(method.upper(),
                                                            url)


class AiohttpClientMockResponse:
    """Mock Aiohttp client response."""

    def __init__(self, method, url, status, response):
        """Initialize a fake response."""
        self.method = method
        self.url = url
        self.status = status
        self.response = response

    def match_request(self, method, url):
        """Test if response answers request."""
        return method == self.method and url == self.url

    @asyncio.coroutine
    def read(self):
        """Return mock response."""
        return self.response

    @asyncio.coroutine
    def text(self, encoding='utf-8'):
        """Return mock response as a string."""
        return self.response.decode(encoding)

    @asyncio.coroutine
    def release(self):
        """Mock release."""
        pass


@contextmanager
def mock_aiohttp_client():
    """Context manager to mock aiohttp client."""
    mocker = AiohttpClientMocker()

    with mock.patch('aiohttp.ClientSession') as mock_session:
        instance = mock_session()

        for method in ('get', 'post', 'put', 'options', 'delete'):
            setattr(instance, method,
                    functools.partial(mocker.match_request, method))

        yield mocker

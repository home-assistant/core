"""Common libraries for test setup."""

import aiohttp
from google_nest_sdm.auth import AbstractAuth
import pytest


class FakeAuth(AbstractAuth):
    """A fake implementation of the auth class that records requests.

    This class captures the outgoing requests, and can also be used by
    tests to set up fake responses.  This class is registered as a response
    handler for a fake aiohttp_server and can simulate successes or failures
    from the API.
    """

    # Tests can set fake responses here.
    responses = []
    # The last request is recorded here.
    method = None
    url = None
    json = None

    # Set up by fixture
    client = None

    def __init__(self):
        """Initialize FakeAuth."""
        super().__init__(None, None)

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return ""

    async def request(self, method, url, json):
        """Capure the request arguments for tests to assert on."""
        self.method = method
        self.url = url
        self.json = json
        return await self.client.get("/")

    async def response_handler(self, request):
        """Handle fake responess for aiohttp_server."""
        if len(self.responses) > 0:
            return self.responses.pop(0)
        return aiohttp.web.json_response()


@pytest.fixture
async def auth(aiohttp_client):
    """Fixture for an AbstractAuth."""
    auth = FakeAuth()
    app = aiohttp.web.Application()
    app.router.add_get("/", auth.response_handler)
    app.router.add_post("/", auth.response_handler)
    auth.client = await aiohttp_client(app)
    return auth

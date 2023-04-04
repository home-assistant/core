"""Test request context middleware."""
from contextvars import ContextVar
from http import HTTPStatus

from aiohttp import web

from homeassistant.components.http.request_context import setup_request_context

from tests.typing import ClientSessionGenerator


async def test_request_context_middleware(
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Test that request context is set from middleware."""
    context = ContextVar("request", default=None)
    app = web.Application()

    async def mock_handler(request):
        """Return the real IP as text."""
        request_context = context.get()
        assert request_context
        assert request_context == request

        return web.Response(text="hi!")

    app.router.add_get("/", mock_handler)
    setup_request_context(app, context)
    mock_api_client = await aiohttp_client(app)

    resp = await mock_api_client.get("/")
    assert resp.status == HTTPStatus.OK

    text = await resp.text()
    assert text == "hi!"

    # We are outside of the context here, should be None
    assert context.get() is None

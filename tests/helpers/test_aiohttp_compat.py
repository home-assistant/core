"""Test the aiohttp compatibility shim."""

import asyncio
from contextlib import suppress

from aiohttp import client, web, web_protocol, web_server
import pytest

from homeassistant.helpers.aiohttp_compat import CancelOnDisconnectRequestHandler


@pytest.mark.allow_hosts(["127.0.0.1"])
async def test_handler_cancellation(socket_enabled, unused_tcp_port_factory) -> None:
    """Test that handler cancels the request on disconnect.

    From aiohttp tests/test_web_server.py
    """
    assert web_protocol.RequestHandler is CancelOnDisconnectRequestHandler
    assert web_server.RequestHandler is CancelOnDisconnectRequestHandler

    event = asyncio.Event()
    port = unused_tcp_port_factory()

    async def on_request(_: web.Request) -> web.Response:
        nonlocal event
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            event.set()
            raise
        else:
            raise web.HTTPInternalServerError()

    app = web.Application()
    app.router.add_route("GET", "/", on_request)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host="127.0.0.1", port=port)

    await site.start()

    try:
        async with client.ClientSession(
            timeout=client.ClientTimeout(total=0.1)
        ) as sess:
            with pytest.raises(asyncio.TimeoutError):
                await sess.get(f"http://127.0.0.1:{port}/")

        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(event.wait(), timeout=1)
        assert event.is_set(), "Request handler hasn't been cancelled"
    finally:
        await asyncio.gather(runner.shutdown(), site.stop())

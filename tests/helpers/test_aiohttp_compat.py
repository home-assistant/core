"""Test the aiohttp compatibility shim."""

import asyncio
from contextlib import suppress

from aiohttp import client, web
import pytest


@pytest.mark.allow_hosts(["127.0.0.1"])
async def test_handler_cancellation(socket_enabled, aiohttp_unused_port) -> None:
    """Test that handler cancels the request on disconnect.

    From aiohttp tests/test_web_server.py
    """
    timeout_event = asyncio.Event()
    done_event = asyncio.Event()
    port = aiohttp_unused_port()

    async def on_request(_: web.Request) -> web.Response:
        nonlocal done_event, timeout_event
        await asyncio.wait_for(timeout_event.wait(), timeout=5)
        done_event.set()
        return web.Response()

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
        await asyncio.sleep(0.1)
        timeout_event.set()

        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(done_event.wait(), timeout=1)
        assert done_event.is_set()
    finally:
        await asyncio.gather(runner.shutdown(), site.stop())

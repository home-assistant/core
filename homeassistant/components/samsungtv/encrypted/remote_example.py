"""SamsungTV Encrypted."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from .remote import SamsungTVEncryptedWSAsyncRemote, SendRemoteKey

logging.basicConfig(level=logging.DEBUG)

_HOST = "192.168.0.14"
_PORT = 8000

_TOKEN = ""
_SESSION_ID = ""


async def main() -> None:
    """Get token."""
    host = _HOST
    port = _PORT
    token = _TOKEN
    session_id = _SESSION_ID

    async with aiohttp.ClientSession() as web_session:
        remote = SamsungTVEncryptedWSAsyncRemote(
            host=host,
            web_session=web_session,
            token=token,
            session_id=session_id,
            port=port,
        )
        await remote.start_listening()

        await remote.send_command(SendRemoteKey.click("KEY_POWER"))

        await asyncio.sleep(15)

        await remote.close()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())

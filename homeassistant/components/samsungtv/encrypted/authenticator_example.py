"""SamsungTV Encrypted."""
from __future__ import annotations

import asyncio

import aiohttp

from .authenticator import SamsungTVEncryptedWSAsyncAuthenticator
from .remote import SamsungTVEncryptedWSAsyncRemote, SendRemoteKey

_HOST = "192.168.0.14"
_PORT = 8000

_TOKEN = ""
_SESSION_ID = ""


async def _get_token(
    host: str, web_session: aiohttp.ClientSession, port: int
) -> tuple[str, str]:
    authenticator = SamsungTVEncryptedWSAsyncAuthenticator(
        host, web_session=web_session, port=port
    )
    await authenticator.start_pairing()
    token: str | None = None
    while not token:
        pin = input("Please enter pin from tv: ")
        token = await authenticator.try_pin(pin)

    session_id = await authenticator.get_session_id_and_close()

    return (token, session_id)


async def main() -> None:
    """Get token."""
    host = _HOST
    port = _PORT
    token = _TOKEN
    session_id = _SESSION_ID

    async with aiohttp.ClientSession() as web_session:
        if not token or not session_id:
            token, session_id = await _get_token(host, web_session, port)
            print(f"Token: '{token}', session: '{session_id}'")

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

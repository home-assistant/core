"""Send a single command to the AVR over a short-lived connection."""

import asyncio
import contextlib
import logging

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, SINGLE_COMMAND_LINGER_SECONDS, SINGLE_COMMAND_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


async def async_send_single_command(host: str, port: int, command: str) -> list[str]:
    """Open a new connection, send one command, wait briefly and close it.

    MRX x10 receivers often ignore input changes sent over the long-lived
    connection, but act on the same command sent over a new connection.

    Returns the replies the receiver sent while the connection was open,
    split on ";".
    """
    _LOGGER.debug("Sending %s over a new connection", command)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), SINGLE_COMMAND_TIMEOUT_SECONDS
        )
    except (OSError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host, "port": str(port)},
        ) from err
    received = b""
    try:
        writer.write(f"{command};".encode())
        await writer.drain()
        # Keep the connection open so the receiver acts on the command, and
        # collect its replies in the meantime.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + SINGLE_COMMAND_LINGER_SECONDS
        while (remaining := deadline - loop.time()) > 0:
            try:
                chunk = await asyncio.wait_for(reader.read(1024), remaining)
            except TimeoutError:
                break
            if not chunk:
                break
            received += chunk
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="send_failed",
        ) from err
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
    replies = [m for m in received.decode(errors="replace").split(";") if m.strip()]
    _LOGGER.debug("Replies to %s: %s", command, replies)
    return replies

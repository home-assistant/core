"""Send a single command to the AVR over a short-lived connection."""

import asyncio
import contextlib
import logging

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, SINGLE_COMMAND_LINGER_SECONDS, SINGLE_COMMAND_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


async def async_send_single_command(host: str, port: int, command: str) -> None:
    """Open a new connection, send one command, wait briefly and close it.

    MRX x10 receivers often ignore input changes sent over the long-lived
    connection, but act on the same command sent over a new connection.
    """
    _LOGGER.debug("Sending %s over a new connection", command)
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), SINGLE_COMMAND_TIMEOUT_SECONDS
        )
    except (OSError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host, "port": str(port)},
        ) from err
    try:
        writer.write(f"{command};".encode())
        await writer.drain()
        await asyncio.sleep(SINGLE_COMMAND_LINGER_SECONDS)
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="send_failed",
        ) from err
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()

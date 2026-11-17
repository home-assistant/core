"""Send commands to the AVR over a short-lived connection."""

import asyncio
from collections.abc import AsyncIterator
import contextlib
import logging

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, SINGLE_COMMAND_LINGER_SECONDS, SINGLE_COMMAND_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


class SingleCommandConnection:
    """A new connection to the AVR, used for one change.

    MRX x10 receivers often ignore changes sent over the long-lived
    connection, but act on the same command sent over a new connection.
    """

    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Initialize with an open connection."""
        self._reader = reader
        self._writer = writer

    async def send(self, command: str, until: str | None = None) -> list[str]:
        """Send a command and return the replies, split on ";".

        Waits so the receiver acts on the command before the connection
        closes, or until a reply equal to `until` arrives.
        """
        _LOGGER.debug("Sending %s over a new connection", command)
        replies: list[str] = []
        buffer = ""
        try:
            self._writer.write(f"{command};".encode())
            await self._writer.drain()
            loop = asyncio.get_running_loop()
            deadline = loop.time() + SINGLE_COMMAND_LINGER_SECONDS
            while (remaining := deadline - loop.time()) > 0:
                try:
                    chunk = await asyncio.wait_for(self._reader.read(1024), remaining)
                except TimeoutError:
                    break
                if not chunk:
                    break
                *complete, buffer = (buffer + chunk.decode(errors="replace")).split(";")
                replies += [reply for reply in complete if reply.strip()]
                if until is not None and until in replies:
                    break
        except OSError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_failed",
            ) from err
        _LOGGER.debug("Replies to %s: %s", command, replies)
        return replies


@contextlib.asynccontextmanager
async def async_single_command_connection(
    host: str, port: int
) -> AsyncIterator[SingleCommandConnection]:
    """Open a new connection to the AVR and close it afterwards."""
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
    try:
        yield SingleCommandConnection(reader, writer)
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()

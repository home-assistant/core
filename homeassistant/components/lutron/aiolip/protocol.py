"""Lutron Protocol."""

import asyncio
from enum import Enum
import re
import time

from .data import LIPMessage, LIPMode, LIPOperation

LIP_PROTOCOL_LOGIN = "login: "
LIP_PROTOCOL_PASSWORD = "password: "
LIP_PROTOCOL_GNET = "GNET> "
LIP_PROTOCOL_QNET = "QNET> "
LIP_PROTOCOL_GENERIC_NET = "NET> "

LIP_USERNAME = "lutron"
LIP_PASSWORD = "integration"
LIP_PORT = 23

LIP_KEEP_ALIVE = "?SYSTEM,10"

CONNECT_TIMEOUT = 10
SOCKET_TIMEOUT = 45  # The bridge can try to do ident which can take up to 30 seconds

LIP_READ_TIMEOUT = 60
LIP_KEEP_ALIVE_INTERVAL = 60


class LIPControllerType(Enum):
    """Lutron controller type."""

    UNKNOWN = 0
    RADIORA2 = 1
    HOMEWORKS = 2


class LIPConnectionState(Enum):
    """Connection state."""

    NOT_CONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2


class LIPSocket:
    """A socket that reads and writes lip protocol."""

    def __init__(self, reader, writer):
        """Initialize the socket."""
        self._writer = writer
        self._reader = reader

    async def async_readline(self, timeout=SOCKET_TIMEOUT):
        """Read one line from the socket."""
        buffer = await asyncio.wait_for(self._reader.readline(), timeout=timeout)
        if buffer == b"":
            return None

        return buffer.decode("UTF-8")

    async def async_readuntil(self, separator, timeout=SOCKET_TIMEOUT):
        """Read until separator is ended."""
        buffer = await asyncio.wait_for(
            self._reader.readuntil(separator.encode("UTF-8")), timeout=timeout
        )
        if buffer == b"":
            return None

        return buffer.decode("UTF-8")

    async def async_write_command(self, text):
        """Write command to lip protocol."""
        self._writer.write(text.encode("UTF-8") + b"\r\n")
        await self._writer.drain()

    def close(self):
        """Cleanup when disconnected."""
        self._writer.close()

    def __del__(self):
        """Cleanup when the object is deleted."""
        self._writer.close()


class LIPParser:
    """Parse a message from the Lutron controller."""

    def __init__(self):
        """Initialize the parser."""
        # Single regex pattern for all modes with optional parameters
        self._pattern = re.compile(r"~(\w+),(\d+),(\d+)(?:,([0-9.]+))?(?:,([0-9.]+))?")

        # Special message types
        self._keepalive_re = re.compile(r"~SYSTEM")
        self._error_re = re.compile(r"~ERROR,(\d+)")
        self._empty_re = re.compile("^[\r\n]+$")
        self._clean_prompt_re = re.compile("^(\x00|\\s*[A-Z]NET>\\s*)+")

        # Internal state
        self._last_keep_alive_response: float = 0.0

    @property
    def last_keepalive(self) -> float:
        """Return last keepalive response."""
        return self._last_keep_alive_response

    def parse(self, response: str) -> LIPMessage | None:
        """Parse a LIP response and update the internal state. Returns a LIPMessage or None."""
        if not response or self._empty_re.match(response):
            return None

        response = self._clean_prompt_re.sub("", response)

        if self._keepalive_re.match(response):
            self._last_keep_alive_response = time.time()
            return LIPMessage(mode=LIPMode.KEEPALIVE, raw=response)

        if self._error_re.match(response):
            return LIPMessage(mode=LIPMode.ERROR, raw=response)

        if not response.startswith(LIPOperation.RESPONSE):
            return None

        try:
            msg = self._parse_message(response)
            msg.raw = response
        except Exception as ex:
            raise ValueError(f"Failed to parse LIP {response} message") from ex
        return msg

    def _parse_message(self, response: str) -> LIPMessage:
        """Unified parser function for all message types."""
        match = self._pattern.match(response)

        if not match:
            raise ValueError(f"Malformed response: {response}")

        mode = LIPMode.from_string(match.group(1))

        if mode == LIPMode.UNKNOWN:
            return LIPMessage(mode=LIPMode.UNKNOWN, raw=response)

        # Extract common fields
        kwargs = {
            "mode": mode,
            "integration_id": int(match.group(2)),  # Always group 2
        }

        # Extract mode-specific fields based on the mode's parser configuration
        for field_name, (group_index, converter) in mode.parser_config.items():
            if group_index is None:
                # Field is always None for this mode
                kwargs[field_name] = None  # type: ignore[assignment]
            else:
                # Extract and convert the value
                raw_value = match.group(group_index)
                kwargs[field_name] = converter(raw_value)

        return LIPMessage(**kwargs)  # type: ignore[arg-type]

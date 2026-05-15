"""Client for Global Caché iTach IP2IR."""

import asyncio
from contextlib import suppress
import logging
import time
from typing import Any

from ._exceptions import (
    ItachBusyError,
    ItachCommandError,
    ItachConnectionError,
    ItachResponseError,
)
from ._protocol import (
    build_completeir_response_prefix,
    build_sendir_command,
    parse_device_line,
    parse_ir_response,
    parse_net_response,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 4998
DEFAULT_TIMEOUT = 10.0
MAX_RESPONSE_LINES = 128
MAX_STALE_SENDIR_COMPLETEIR_LINES = 8
IDLE_CONNECTION_TIMEOUT = 15.0


class _ItachWriteConnectionError(ItachConnectionError):
    """Connection error raised when writing or flushing a command fails."""


class ItachClient:
    """Client for the Global Caché iTach TCP API."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize client."""
        self._host = host
        self._port = port
        self._timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._next_sendir_command_id = 1
        self._last_used_monotonic: float | None = None
        self.max_connector: int | None = None

    async def async_connect(self) -> None:
        """Open TCP connection."""
        if self._is_connected():
            return

        if self._reader is not None or self._writer is not None:
            await self.close()

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout,
            )
        except (OSError, TimeoutError) as err:
            raise ItachConnectionError(
                f"Could not connect to iTach at {self._host}:{self._port}"
            ) from err

    async def close(self) -> None:
        """Close TCP connection."""
        if self._writer is not None:
            self._writer.close()
            wait_closed = getattr(self._writer, "wait_closed", None)
            if callable(wait_closed):
                with suppress(OSError):
                    await wait_closed()

        self._reader = None
        self._writer = None
        self._last_used_monotonic = None

    async def _ensure_connected_fresh_locked(self) -> None:
        """Ensure there is a usable connection while caller holds the lock."""
        if not self._is_connected():
            await self.async_connect()
            return

        if not self._connection_is_idle_stale():
            return

        _LOGGER.debug(
            "Closing idle iTach connection before reuse for %s:%s",
            self._host,
            self._port,
        )
        await self.close()
        await self.async_connect()

    def _is_connected(self) -> bool:
        """Return true if the cached stream objects are usable."""
        if self._reader is None or self._writer is None:
            return False

        is_closing = getattr(self._writer, "is_closing", None)
        if callable(is_closing):
            return not bool(is_closing())

        return True

    def _connection_is_idle_stale(self) -> bool:
        """Return true if the open connection has been idle too long to trust."""
        if self._last_used_monotonic is None:
            return False

        return time.monotonic() - self._last_used_monotonic > IDLE_CONNECTION_TIMEOUT

    async def _write_command_locked(self, command: str) -> None:
        """Write a command while caller holds the lock."""
        if self._writer is None:
            raise ItachConnectionError("Connection is not open")

        _LOGGER.debug(
            "Sending iTach command to %s:%s: %r",
            self._host,
            self._port,
            command,
        )

        try:
            self._writer.write(command.encode("ascii"))
            await self._writer.drain()
        except OSError as err:
            await self.close()
            raise _ItachWriteConnectionError("Failed sending command to iTach") from err

    async def _read_response_line(self) -> str:
        """Read one iTach response terminated by carriage return."""
        if self._reader is None:
            raise ItachConnectionError("Connection is not open")

        try:
            raw = await asyncio.wait_for(
                self._reader.readuntil(b"\r"),
                timeout=self._timeout,
            )
        except TimeoutError as err:
            await self.close()
            raise ItachConnectionError("Timed out waiting for iTach response") from err
        except asyncio.IncompleteReadError as err:
            await self.close()
            raise ItachConnectionError("Incomplete response from iTach") from err
        except OSError as err:
            await self.close()
            raise ItachConnectionError(
                "Socket error while reading iTach response"
            ) from err

        return raw.decode("utf-8", errors="replace").strip()

    def _allocate_sendir_command_id(self) -> int:
        """Allocate a sendir command id.

        Changing ids let us distinguish the current completeir from stale
        completeir responses still buffered on the TCP stream.
        """
        command_id = self._next_sendir_command_id
        self._next_sendir_command_id += 1

        if self._next_sendir_command_id > 65535:
            self._next_sendir_command_id = 1

        return command_id

    async def send_command(self, command: str) -> str:
        """Send a raw iTach command and return one response line.

        Commands are not retried after write or response failures. Once bytes
        are handed to the stream writer, the device may already have received
        and acted on the command, so retrying can duplicate side effects.
        """
        async with self._lock:
            return await self._send_command_locked(command)

    async def _send_command_locked(self, command: str) -> str:
        """Send a raw iTach command while caller holds the lock."""
        await self._ensure_connected_fresh_locked()
        await self._write_command_locked(command)

        response = await self._read_response_line()
        self._last_used_monotonic = time.monotonic()

        _LOGGER.debug(
            "Received iTach response from %s:%s: %s",
            self._host,
            self._port,
            response,
        )

        return response

    async def async_get_version(self, module: int = 1) -> str:
        """Fetch the version string for a module."""
        command = f"getversion,{module}\r"
        response = await self.send_command(command)

        if response.startswith("ERR"):
            raise ItachCommandError(response, command)

        return response

    async def async_get_net(self) -> str:
        """Fetch network configuration as a raw response string."""
        command = "get_NET,0:1\r"
        response = await self.send_command(command)

        if response.startswith("ERR"):
            raise ItachCommandError(response, command)

        if not response.startswith("NET,"):
            raise ItachResponseError(f"Malformed get_NET response: {response}")

        return response

    async def async_get_net_info(self) -> dict[str, Any]:
        """Fetch parsed network configuration.

        The iTach firmware has emitted several get_NET variants over time. This
        parser intentionally preserves unknown trailing fields instead of trying
        to overfit one firmware version.
        """
        response = await self.async_get_net()
        return parse_net_response(response)

    async def async_get_devices(self) -> list[str]:
        """Fetch device list."""
        return await self._async_get_multiline_response(
            command="getdevices\r",
            terminator="endlistdevices",
        )

    async def _async_get_multiline_response(
        self,
        *,
        command: str,
        terminator: str,
    ) -> list[str]:
        """Fetch a terminated multiline iTach response.

        Do not retry after a write or read failure. The command may already
        have reached the device, and a retry can interleave stale lines from
        the first request with the second response.
        """
        response_lines: list[str] = []

        async with self._lock:
            return await self._async_get_multiline_response_locked(
                command=command,
                terminator=terminator,
                response_lines=response_lines,
            )

    async def _async_get_multiline_response_locked(
        self,
        *,
        command: str,
        terminator: str,
        response_lines: list[str],
    ) -> list[str]:
        """Fetch multiline response while caller holds the lock."""
        await self._ensure_connected_fresh_locked()
        await self._write_command_locked(command)

        for _ in range(MAX_RESPONSE_LINES):
            line = await self._read_response_line()

            if line.startswith("ERR"):
                raise ItachCommandError(line, command)

            if line == terminator:
                self._last_used_monotonic = time.monotonic()
                return response_lines

            if terminator in line:
                before_end = line.split(terminator, 1)[0].strip()
                if before_end:
                    response_lines.append(before_end)
                self._last_used_monotonic = time.monotonic()
                return response_lines

            if line:
                response_lines.append(line)

        raise ItachResponseError(
            f"Terminator {terminator!r} not received for {command.strip()}"
        )

    async def async_get_ir_module(self) -> tuple[int, int]:
        """Return the IR module number and number of IR connectors."""
        devices = await self.async_get_devices()

        for line in devices:
            parsed = parse_device_line(line)
            if parsed is None:
                _LOGGER.debug("Skipping malformed getdevices line: %s", line)
                continue

            if parsed["type"] == "IR":
                return int(parsed["module"]), int(parsed["ports"])

        raise ItachCommandError("No IR module found", "getdevices\r")

    async def async_get_ir_connector_modes(
        self,
        module: int,
        ports: int,
    ) -> dict[int, str]:
        """Return configured mode for each IR connector."""
        if module < 1:
            raise ValueError("Module must be >= 1")

        if ports < 1:
            raise ValueError("Ports must be >= 1")

        modes: dict[int, str] = {}

        for connector in range(1, ports + 1):
            command = f"get_IR,{module}:{connector}\r"
            response = await self.send_command(command)

            if response.startswith("ERR"):
                _LOGGER.debug(
                    "Unable to get IR connector mode for %s:%s: %s",
                    module,
                    connector,
                    response,
                )
                continue

            parsed = parse_ir_response(response)
            if parsed is None:
                _LOGGER.debug(
                    "Skipping malformed get_IR response for %s:%s: %s",
                    module,
                    connector,
                    response,
                )
                continue

            response_module, response_connector, mode = parsed
            if response_module != module or response_connector != connector:
                _LOGGER.debug(
                    "Ignoring get_IR response for unexpected connector. "
                    "expected=%s:%s received=%s:%s response=%s",
                    module,
                    connector,
                    response_module,
                    response_connector,
                    response,
                )
                continue

            modes[connector] = mode

        return modes

    async def async_send_ir(
        self,
        module: int,
        connector: int,
        carrier_frequency: int,
        timings: list[int],
        *,
        repeat: int = 1,
        offset: int = 1,
        command_id: int | None = None,
    ) -> None:
        """Send an IR command using Global Caché sendir.

        Waits for the matching completeir response. Stale/unrelated completeir
        responses are ignored.
        """
        if command_id is None:
            command_id = self._allocate_sendir_command_id()

        self._validate_sendir_args(
            module=module,
            connector=connector,
            carrier_frequency=carrier_frequency,
            timings=timings,
            repeat=repeat,
            offset=offset,
            command_id=command_id,
        )

        command = build_sendir_command(
            module=module,
            connector=connector,
            command_id=command_id,
            carrier_frequency=carrier_frequency,
            repeat=repeat,
            offset=offset,
            timings=timings,
        )

        _LOGGER.debug("SENDIR COMMAND: %s", command.strip())

        expected_complete = build_completeir_response_prefix(
            module=module,
            connector=connector,
            command_id=command_id,
        )

        async with self._lock:
            await self._send_ir_locked(
                command=command,
                expected_complete=expected_complete,
            )

    async def _send_ir_locked(
        self,
        *,
        command: str,
        expected_complete: str,
    ) -> None:
        """Send one sendir command while caller holds the lock."""
        await self._ensure_connected_fresh_locked()
        await self._write_command_locked(command)
        response = await self._read_response_line()
        await self._handle_sendir_response(
            response=response,
            expected_complete=expected_complete,
            command=command,
        )
        self._last_used_monotonic = time.monotonic()

    async def _handle_sendir_response(
        self,
        *,
        response: str,
        expected_complete: str,
        command: str,
    ) -> None:
        """Handle sendir responses until the matching completeir is received."""
        for _ in range(MAX_STALE_SENDIR_COMPLETEIR_LINES + 1):
            response_lower = response.lower()

            if response_lower.startswith("busyir"):
                raise ItachBusyError(response)

            if response.startswith("ERR"):
                _LOGGER.warning(
                    "Command rejected by iTach. response=%s command=%s",
                    response,
                    command.strip(),
                )
                raise ItachCommandError(response, command)

            if _completeir_matches(response, expected_complete):
                return

            if response_lower.startswith("completeir"):
                _LOGGER.debug(
                    "Ignoring stale/unrelated completeir response. expected=%s "
                    "received=%s",
                    expected_complete,
                    response,
                )
                try:
                    response = await self._read_response_line()
                except ItachConnectionError as err:
                    raise ItachResponseError(
                        f"Matching {expected_complete!r} not received for sendir command"
                    ) from err
                continue

            raise ItachCommandError(response, command)

        raise ItachResponseError(
            f"Matching {expected_complete!r} not received for sendir command"
        )

    def _validate_sendir_args(
        self,
        *,
        module: int,
        connector: int,
        carrier_frequency: int,
        timings: list[int],
        repeat: int,
        offset: int,
        command_id: int,
    ) -> None:
        """Validate sendir arguments."""
        if module < 1:
            raise ValueError("Module must be >= 1")

        if connector < 1:
            raise ValueError("Connector must be >= 1")

        if self.max_connector is not None and connector > self.max_connector:
            raise ValueError(f"Connector must be between 1 and {self.max_connector}")

        if not (0 <= command_id <= 65535):
            raise ValueError("Command ID must be between 0 and 65535")

        if not (15000 <= carrier_frequency <= 500000):
            raise ValueError("Carrier frequency must be between 15000 and 500000 Hz")

        if not (1 <= repeat <= 50):
            raise ValueError("Repeat must be between 1 and 50")

        if offset < 1 or offset % 2 == 0:
            raise ValueError("Offset must be a positive odd number")

        if not timings:
            raise ValueError("Timings list cannot be empty")

        if len(timings) % 2 != 0:
            raise ValueError("Timings list must contain on/off pairs")

        if any(value <= 0 for value in timings):
            raise ValueError("All timing values must be > 0")


def _parse_completeir_response(response: str) -> tuple[int, int, int] | None:
    """Parse a completeir response into module, connector, and command id."""
    parts = [part.strip() for part in response.strip().split(",")]
    if len(parts) < 3 or parts[0].lower() != "completeir":
        return None

    address_parts = parts[1].split(":", 1)
    if len(address_parts) != 2:
        return None

    try:
        module = int(address_parts[0].strip())
        connector = int(address_parts[1].strip())
        command_id = int(parts[2].strip())
    except ValueError:
        return None

    if module < 1 or connector < 1 or command_id < 0:
        return None

    return module, connector, command_id


def _completeir_matches(response: str, expected_complete: str) -> bool:
    """Return true when response is the expected completeir notification."""
    parsed_response = _parse_completeir_response(response)
    if parsed_response is None:
        return False

    parsed_expected = _parse_completeir_response(expected_complete)
    if parsed_expected is None:
        return False

    return parsed_response == parsed_expected

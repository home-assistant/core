"""The KinCony Hx integration."""
from __future__ import annotations

import logging
import socket
import threading
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady

from .const import (
    CONF_SO_TIMEOUT,
    DATA_KCBOARD,
    DEFAULT_PORT,
    DEFAULT_SO_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

PLATFORMS: list[Platform] = [Platform.SWITCH]


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class ResponseError(HomeAssistantError):
    """Error to indicate protocol error."""


def _status_from_resp(resp: str) -> bool:
    """Retrieve that response status on success, raises ResponseError otherwise."""
    resp_parts = resp.split(",")
    succ = resp_parts.pop(-1).strip().lower()
    status = int(resp_parts.pop(-1))

    if not succ.startswith("ok"):
        raise ResponseError(succ, status, resp)

    _LOGGER.debug("Got response %s with status %s", succ, status)
    return 1 == status


class KCBoard:
    """Wrapper over raw socket to remote KinCony Board."""

    _socket: socket.socket
    _sn: str | None = None
    _relays_count: int | None = None

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        so_timeout: float = DEFAULT_SO_TIMEOUT,
    ) -> None:
        """Create a remote client for KinCony Board endpoint."""
        self._host = host
        self._port = port
        self._so_timeout = so_timeout
        self._lock = threading.Lock()

    def connect(self):
        """Request remote connection at init time."""
        remote_ip = self._host
        try:
            remote_ip = socket.gethostbyname(self._host)
            _LOGGER.info("Hostname %s resolved to IP %s", self._host, remote_ip)
        except socket.gaierror:
            _LOGGER.warning("Hostname %s could not be resolved", self._host)

        if hasattr(self, "_socket"):
            try:
                self._socket.close()
            except OSError:
                pass

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(self._so_timeout)
        self._socket.connect((remote_ip, self._port))
        _LOGGER.info("Connection successful to %s:%s", self._host, self._port)

    def dispose(self):
        """Close remote connection and invalidates this instance."""
        if hasattr(self, "_socket"):
            try:
                self._socket.close()
            finally:
                self._socket = None

    def _send(self, command: str) -> None:
        self._socket.send(command.encode("utf-8"))

    def _receive(self) -> str:
        return self._socket.recv(1024).decode("utf-8")

    def _request(self, command: str, retry_count: int = 3) -> str:
        """Make a request to remote board with specified command."""

        with self._lock:
            try:
                self._send(command)
                # time.sleep(1)
                return self._receive()
            except OSError as err:
                if retry_count > 0:
                    # reconnect and retry
                    # time.sleep(3)
                    self.connect()
                    return self._request(command, retry_count=retry_count - 1)
                raise CannotConnect from err

    def get_board_host(self) -> str:
        """Get the board Host/IP endpoint address."""
        return self._host

    def read_serial_num(self) -> str:
        """Get the board identifier note, this starts testing of all ports."""

        if self._sn is None:
            self._sn = self._request("RELAY-HOST-NOW").split("-").pop()

        return self._sn

    def read_relays_count(self) -> int:
        """Make a request to find the max number of relay switches."""

        if self._relays_count is None:
            self._relays_count = int(
                self._request("RELAY-SCAN_DEVICE-NOW")
                .split(",")
                .pop(0)
                .split("_")
                .pop()
            )

        return self._relays_count

    def read_relay_status(self, index: int) -> bool:
        """Retrieve the status of a Relay Switch - index is 0-based."""
        _LOGGER.debug("Reading SW %s status", index + 1)
        return _status_from_resp(self._request(f"RELAY-READ-255,{index + 1}"))

    def write_relay_status(self, index: int, status: bool = True) -> bool:
        """Set the status of a Relay Switch - index is 0-based."""
        _LOGGER.debug("Setting SW %s to status %s", index + 1, status)
        return _status_from_resp(
            self._request(f"RELAY-SET-255,{index + 1},{1 if status else 0}")
        )

    @staticmethod
    def from_data(data: dict[str, Any] | MappingProxyType[str, Any]) -> KCBoard:
        """Create new instance from a data dict using this factory method."""
        host = data[CONF_HOST]
        port = data[CONF_PORT]
        so_timeout = data[CONF_SO_TIMEOUT]
        return KCBoard(host, port, so_timeout)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KinCony Hx from a config entry."""

    client = KCBoard.from_data(entry.data)

    try:
        client.connect()
    except OSError as exception:
        raise PlatformNotReady from exception

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_KCBOARD: client}

    # Setup components
    entry.title = entry.data[CONF_NAME]
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class KCSwitch:
    """Base KinKony Switch class."""

    def __init__(self, board: KCBoard, index: int) -> None:
        """Create a switch instance."""
        super().__init__()
        self._board = board
        self._index = index

    def get_uuid(self):
        """Get a unique identifier for this entity."""
        return f"{self._board.get_board_host()}/sw.{self._index}"

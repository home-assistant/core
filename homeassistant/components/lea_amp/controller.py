"""Controller."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import socket
from typing import Any

from .const import DISCOVERY_INTERVAL, PORT, UPDATE_INTERVAL
from .message import (
    DevStatusResponse,
    GetModelMessage,
    MessageResponseFactory,
    OnOffMessage,
    ZoneEnabledMsg,
    getMuteMessage,
    getSourceMessage,
    getVolumeMessage,
    setMuteMessage,
    setSourceMessage,
    setVolumeMessage,
)
from .zone import LeaZone
from .zone_registry import ZoneRegistry

_LOGGER = logging.getLogger(__name__)


class LeaController:
    """LEA Controller."""

    def __init__(  # noqa: D417
        self,
        loop=None,
        port: str = PORT,
        ip_address: str = "",
        discovery_enabled: bool = False,
        discovery_interval: int = DISCOVERY_INTERVAL,
        update_enabled: bool = True,
        update_interval: int = UPDATE_INTERVAL,
        discovered_callback: Callable[[LeaZone, bool], bool] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Build a controller that handle Lea zones that support local API on local network.

        Args:
            loop: The asyncio event loop. If None the loop is retrieved by calling ``asyncio.get_running_loop()``

            discovery_enabled (bool): If true a discovery message is sent every ``discovery_interval`` seconds. Default: False
            update_enabled (bool): If true the zones status is updated automatically every ``update_interval`` seconds. A successful zone update reset the eviction timer for the zone. Default: True
            update_interval (int): Interval between a status update is requested to zones.
            discovered_callback (Callable[LeaZone, bool]): An optional function to call when a zone is discovered (or rediscovered). Default None

        """
        self._logger = logger or logging.getLogger(__name__)

        self._transport: Any = None
        self._protocol = None

        self._port = port
        self._ip_address = ip_address

        self._loop = loop or asyncio.get_running_loop()
        self._cleanup_done: asyncio.Event = asyncio.Event()
        self._message_factory = MessageResponseFactory()
        self._registry: ZoneRegistry = ZoneRegistry(self._logger)

        self._discovery_enabled = discovery_enabled
        self._discovery_interval = discovery_interval
        self._update_enabled = update_enabled
        self._update_interval = update_interval

        self._zone_discovered_callback = discovered_callback

        self._discovery_handle: asyncio.TimerHandle | None = None
        self._update_handle: asyncio.TimerHandle | None = None

        self._response_handler: dict[str, Callable] = {
            # GetNumOfInputsMessage: self._handle_num_inputs,
            DevStatusResponse.command: self._handle_response_received,
        }

    async def createConnection(self):
        """Create Connection."""

        self._transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        address = (self._ip_address, int(self._port))
        self._transport.connect(address)
        _LOGGER.log(logging.INFO, "Connected to %s", address)
        _LOGGER.log(logging.INFO, "Discover enabled %s", str(self._discovery_enabled))
        _LOGGER.log(logging.INFO, "Update enabled %s", str(self._update_enabled))

    async def start(self):
        """Start."""

        await self.createConnection()
        # self._discovery_enabled = False
        # self._update_enabled = True
        if self._discovery_enabled or self._registry.has_queued_zones:
            self.send_discovery_message()
        if self._update_enabled:
            self.send_update_message()
        # self.start_client(self._ip_address, int(self._port))

    def cleanup(self) -> asyncio.Event:
        """Stop discovering. Stop updating. Close connection."""
        self._cleanup_done.clear()
        self.set_update_enabled(False)
        self.set_discovery_enabled(False)

        if self._transport:
            self._transport.close()
        self._registry.cleanup()
        return self._cleanup_done

    def add_zone_to_discovery_queue(self, zone_id: str) -> bool:
        """Add zone to queue."""
        zone_added: bool = self._registry.add_zone_to_queue(int(zone_id))
        if not self._discovery_enabled and zone_added:
            self.send_discovery_message()
        return zone_added

    def remove_zone_from_discovery_queue(self, zone_id: str) -> bool:
        """Remove zone from queue."""
        return self._registry.remove_zone_from_queue(int(zone_id))

    @property
    def discovery_queue(self):
        """Return zones queue."""
        return self._registry.zones_queue

    def remove_zone(self, zone: str | LeaZone) -> None:
        """Remove Zone."""
        if isinstance(zone, LeaZone):
            zone = zone.zone_id
        self._registry.remove_discovered_zone(zone)

    def set_discovery_enabled(self, enabled: bool) -> None:
        """Enable Discovery."""
        if self._discovery_enabled == enabled:
            return
        self._discovery_enabled = enabled
        if enabled:
            self.send_discovery_message()
        elif self._discovery_handle:
            self._discovery_handle.cancel()
            self._discovery_handle = None

    @property
    def discovery(self) -> bool:
        """Return that discover is enabled."""
        return self._discovery_enabled

    def set_discovery_interval(self, interval: int) -> None:
        """Set Discovery Interval."""
        self._discovery_interval = interval

    @property
    def discovery_interval(self) -> int:
        """Return Discovrey Interval."""
        return self._discovery_interval

    def set_zone_discovered_callback(
        self, callback: Callable[[LeaZone, bool], bool] | None
    ) -> Callable[[LeaZone, bool], bool] | None:
        """Set Zone Discovered callback."""
        old_callback = self._zone_discovered_callback
        self._zone_discovered_callback = callback
        return old_callback

    def set_update_enabled(self, enabled: bool) -> None:
        """Enable update."""
        if self._update_enabled == enabled:
            return
        self._update_enabled = enabled
        if enabled:
            self.send_update_message()
        elif self._update_handle:
            self._update_handle.cancel()
            self._update_handle = None

    @property
    def update_enabled(self) -> bool:
        """Return updates is enabled."""
        return self._update_enabled

    def send_discovery_message(self) -> None:
        """Send Get Number of Inputs."""
        message: str = str(GetModelMessage())
        _LOGGER.log(logging.INFO, "Sending discovery message: %s", message)

        if not self._transport:
            _LOGGER.log(logging.INFO, "Transport not available")
            self.createConnection()
            return
        _LOGGER.log(logging.INFO, "Discovery enabled: %s", str(self._discovery_enabled))
        if self._discovery_enabled:
            self._transport.send(message.encode())
            # while True:
            data = self._transport.recv(2048)
            if data:
                _LOGGER.log(logging.INFO, "response data: %s", str(data))
                self._handle_num_inputs(data.decode())
                # self._handle_response_received(data)
            # self._transport.close()
        if self._registry.has_queued_zones:
            for zone_id in self._registry.zones_queue:
                self._transport.sendto(message, (zone_id, self._port))

    def send_update_message(self) -> None:
        """Send Update Message."""

        if self._transport:
            for d in self._registry.discovered_zones.values():
                _LOGGER.log(logging.INFO, "zone id: %s", str(d.zone_id))
                self._send_update_message(d.zone_id)

            if self._update_enabled:
                self._update_handle = self._loop.call_later(
                    self._update_interval, self.send_update_message
                )

    async def turn_on_off(self, zone_id: str, status: str):
        """Turn on off."""
        self._send_message(OnOffMessage(zone_id, status))
        self._send_update_message(zone_id)

    async def set_volume(self, zone_id: str, volume: int) -> None:
        """Set Volume."""
        self._send_message(setVolumeMessage(zone_id, volume))
        self._send_update_message(zone_id)

    async def set_source(self, zone_id: str, source: str) -> None:
        """Set Source."""
        self._send_message(setSourceMessage(zone_id, source))
        self._send_update_message(zone_id)

    async def set_mute(self, zone_id: str, mute: bool) -> None:
        """Set Mute."""
        self._send_message(setMuteMessage(zone_id, mute))
        self._send_update_message(zone_id)

    def get_zone_by_id(self, zone_id: str) -> LeaZone | None:
        """Get Zone by id."""
        _LOGGER.log(logging.INFO, "get_zone_by_id: %s", str(zone_id))
        return self._registry.get_zone_by_zone_id(int(zone_id))

    @property
    def zones(self) -> list[LeaZone]:
        """Return zones."""
        _LOGGER.log(logging.INFO, "controller zones")
        return list(self._registry.discovered_zones.values())

    def connection_lost(self, *args, **kwargs) -> None:
        """Connection Lost."""  # noqa: D401
        self._cleanup_done.set()
        self._logger.debug("Disconnected")

    def _handle_response_received(self, data: str):
        """Handle received response."""
        _LOGGER.log(logging.INFO, "_handle_response_received: %s", str(data))
        zone_id, commandType, value = self._message_factory.create_message(data)

        if zone := self.get_zone_by_id(zone_id):
            _LOGGER.log(logging.INFO, "zone found")
            # zoneInstance = LeaZone(self, zone.zone_id)
            if commandType == "volume":
                _LOGGER.log(logging.INFO, "update volume")
                zone.updateVolume(float(value))
            else:
                _LOGGER.log(logging.INFO, "update")
                zone.update(value, commandType)

    def _handle_num_inputs(self, value: str):
        _LOGGER.log(logging.INFO, "_handle_num_inputs: %s", str(value))
        if "8D" in value or "8N" in value:
            zonesRange = 9
            if "8D" in value:
                model = "8D"
                sourcesList = [
                    "Analog 1",
                    "Analog 2",
                    "Analog 1+2",
                    "Analog 3",
                    "Analog 4",
                    "Analog 3+4",
                    "Analog 5",
                    "Analog 6",
                    "Analog 5+6",
                    "Analog 7",
                    "Analog 8",
                    "Analog 7+8",
                    "Dante 1",
                    "Dante 2",
                    "Dante 1+2",
                    "Dante 3",
                    "Dante 4",
                    "Dante 3+4",
                    "Dante 5",
                    "Dante 6",
                    "Dante 5+6",
                    "Dante 7",
                    "Dante 8",
                    "Dante 7+8",
                ]
            else:
                model = "8N"
                sourcesList = [
                    "Analog 1",
                    "Analog 2",
                    "Analog 1+2",
                    "Analog 3",
                    "Analog 4",
                    "Analog 3+4",
                    "Analog 5",
                    "Analog 6",
                    "Analog 5+6",
                    "Analog 7",
                    "Analog 8",
                    "Analog 7+8",
                ]
        elif "4D" in value or "4N" in value:
            zonesRange = 5
            if "4D" in value:
                model = "4D"
                sourcesList = [
                    "Analog 1",
                    "Analog 2",
                    "Analog 1+2",
                    "Analog 3",
                    "Analog 4",
                    "Analog 3+4",
                    "Dante 1",
                    "Dante 2",
                    "Dante 1+2",
                    "Dante 3",
                    "Dante 4",
                    "Dante 3+4",
                    "Dante 5",
                    "Dante 6",
                    "Dante 5+6",
                    "Dante 7",
                    "Dante 8",
                    "Dante 7+8",
                ]
            else:
                model = "4N"
                sourcesList = [
                    "Analog 1",
                    "Analog 2",
                    "Analog 1+2",
                    "Analog 3",
                    "Analog 4",
                    "Analog 3+4",
                ]
        elif "2D" in value or "2N" in value:
            zonesRange = 3
            if "2D" in value:
                model = "2D"
                sourcesList = [
                    "Analog 1",
                    "Analog 2",
                    "Analog 1+2",
                    "Dante 1",
                    "Dante 2",
                    "Dante 1+2",
                    "Dante 3",
                    "Dante 4",
                    "Dante 3+4",
                    "Dante 5",
                    "Dante 6",
                    "Dante 5+6",
                    "Dante 7",
                    "Dante 8",
                    "Dante 7+8",
                ]
            else:
                model = "2N"
                sourcesList = ["Analog 1", "Analog 2", "Analog 1+2"]
        for i in range(1, zonesRange):
            zone = LeaZone(self, str(i))
            zone._sourcesList = sourcesList  # noqa: SLF001
            zone._model = model  # noqa: SLF001
            if self._call_discovered_callback(zone, True):
                zone = self._registry.add_discovered_zone(zone)
                _LOGGER.log(logging.INFO, "zone discovered: %s", zone)
            else:
                _LOGGER.log(logging.INFO, "zone %s ignored", zone)

    def _call_discovered_callback(self, zone: LeaZone, is_new: bool) -> bool:
        if not self._zone_discovered_callback:
            return True
        return self._zone_discovered_callback(zone, is_new)

    def _send_message(self, message: str) -> None:
        _LOGGER.log(logging.INFO, "_send_message message:%s", message)
        if not self._transport:
            _LOGGER.log(logging.INFO, "Transport not available")
            self.createConnection()
            return
        self._transport.send(message.encode())
        data = self._transport.recv(2048)
        if data:
            _LOGGER.log(logging.INFO, "response data: %s", str(data))
            if "OK" not in data.decode():
                self._handle_response_received(data.decode())

    def _send_update_message(self, zone_id: str):
        self._send_message(ZoneEnabledMsg(zone_id))
        self._send_message(getMuteMessage(zone_id))
        self._send_message(getVolumeMessage(zone_id))
        self._send_message(getSourceMessage(zone_id))
        # self._send_message(getZoneName(zone_id))

    def start_client(self, host, port):
        """Start Client."""
        # Create a TCP/IP socket
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Connect to the server
        client_socket.connect((host, port))
        # Send some data
        client_socket.sendall(b"subscribe /amp/channels/1/output/mute")
        # Receive the response from the server
        data = client_socket.recv(1024)
        _LOGGER.log(logging.INFO, "response data: %s", str(data))

    def _subscribe_message(self, zone_id: str):
        self._send_message("subscribe /amp/channels/" + zone_id + "/output/mute")
        self._send_message("subscribe /amp/channels/" + zone_id + "/output/fader")
        self._send_message("subscribe /amp/channels/" + zone_id + "/output/enable")
        self._send_message(
            "subscribe /amp/channels/" + zone_id + "/inputSelector/primary"
        )

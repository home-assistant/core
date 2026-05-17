"""Coordinator module for the AirTouch 3 integration."""

import asyncio
import contextlib
import logging
from typing import Any

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .comms.airtouch_aircon import Aircon
from .comms.airtouch_message import AirTouchMessage
from .comms.enums import ZoneStatus
from .comms.message_constants import MessageConstants
from .comms.message_response_parser import MessageResponseParser
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

COMMAND_QUEUE_INTERVAL = 5
DEFAULT_PORT = 8899
RESPONSE_TIMEOUT = 10
MIN_RESPONSE_LENGTH = (
    MessageConstants.AIRTOUCH_ID_START + MessageConstants.AIRTOUCH_ID_LENGTH
)


async def async_fetch_airtouch_data(host: str, port: int = DEFAULT_PORT) -> Aircon:
    """Fetch and parse data from an AirTouch 3 controller."""
    socket_writer: asyncio.StreamWriter | None = None
    try:
        _LOGGER.debug("Fetching AirTouch 3 data from %s:%s", host, port)
        async with asyncio.timeout(RESPONSE_TIMEOUT):
            socket_reader, socket_writer = await asyncio.open_connection(host, port)
            message = AirTouchMessage()
            socket_writer.write(message.get_init_msg())
            await socket_writer.drain()
            response_data = await socket_reader.read(1024)

        _LOGGER.debug(
            "Received %s bytes from AirTouch 3 controller at %s:%s",
            len(response_data),
            host,
            port,
        )
        if len(response_data) < MIN_RESPONSE_LENGTH:
            _LOGGER.debug(
                "AirTouch 3 response from %s:%s was too short: %s bytes",
                host,
                port,
                len(response_data),
            )
            raise UpdateFailed(
                f"AirTouch response was too short: {len(response_data)} bytes"
            )

        parser = MessageResponseParser(bytearray(response_data), _LOGGER)
        return parser.parse()
    except (TimeoutError, OSError, ValueError, IndexError) as err:
        _LOGGER.debug("AirTouch 3 communication with %s:%s failed: %s", host, port, err)
        raise UpdateFailed(f"Communication error with AirTouch: {err}") from err
    finally:
        if socket_writer:
            socket_writer.close()
            with contextlib.suppress(OSError):
                await socket_writer.wait_closed()


class Airtouch3DataUpdateCoordinator(DataUpdateCoordinator[Aircon]):
    """Class to manage fetching Airtouch 3 data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Initialize the Airtouch data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._entry = entry
        self.host = host
        self.port = port
        self.connected = False
        self.socket_reader: asyncio.StreamReader | None = None
        self.socket_writer: asyncio.StreamWriter | None = None
        self._socket_lock = asyncio.Lock()
        self._command_queue: asyncio.Queue[tuple[bytearray, str, int, Any]] = (
            asyncio.Queue()
        )
        self._command_queue_interval = COMMAND_QUEUE_INTERVAL
        self._command_queue_task: asyncio.Task[None] | None = None
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)

    @property
    def system_id(self) -> str:
        """Return a stable controller identifier for entity unique IDs."""
        return self._entry.unique_id or self.host

    async def connect_to_airtouch(self) -> None:
        """Establish a connection to the AirTouch unit."""
        try:
            async with asyncio.timeout(RESPONSE_TIMEOUT):
                self.socket_reader, self.socket_writer = await asyncio.open_connection(
                    self.host, self.port
                )
            self.connected = True
            _LOGGER.debug("Connected to AirTouch unit at %s:%s", self.host, self.port)
        except (TimeoutError, OSError) as e:
            self.connected = False
            raise UpdateFailed(f"Connection to AirTouch failed: {e}") from e

    async def _async_update_data(self) -> Aircon:
        """Fetch data from AirTouch."""
        async with self._socket_lock:
            parsed_data = await async_fetch_airtouch_data(self.host, self.port)
            return self._update_data_from_parsed_response(parsed_data)

    def _update_data_from_parsed_response(self, parsed_data: Aircon) -> Aircon:
        """Update self.data with parsed response information using the parsed Aircon object directly."""
        # Extract groups and temperatures
        parsed_data.groups = [
            {"id": zone.id, "name": zone.name} for zone in parsed_data.zones
        ]
        parsed_data.group_temperatures = {
            zone.id: zone.sensor.current_temperature
            for zone in parsed_data.zones
            if zone.sensor and zone.sensor.is_available
        }
        parsed_data.group_target_temperatures = {
            zone.id: zone.desired_temperature for zone in parsed_data.zones
        }
        parsed_data.group_power_states = {
            zone.id: zone.status == ZoneStatus.ZONE_ON for zone in parsed_data.zones
        }
        return parsed_data

    async def send_command(
        self, command_type: str, target_id: int, value: Any = None
    ) -> None:
        """Send a command to the AirTouch unit."""
        command_key = command_type
        if hasattr(command_key, "value"):
            command_key = command_key.value
        if not isinstance(command_key, str):
            command_key = str(command_key)

        message = AirTouchMessage()
        brand_id = self.data.brand_id
        msg = None

        if command_key == "set_mode":
            msg = message.set_mode(target_id, brand_id, value)
        elif command_key == "set_fan_speed":
            msg = message.set_fan_speed(target_id, brand_id, value)
        elif command_key == "set_group_temperature":
            msg = message.set_fan(target_id, value)
        elif command_key == "turn_on":
            if not self.data.status:
                msg = message.toggle_ac_on_off(target_id)
                _LOGGER.debug("AC is off, queueing turn_on command")
                self.data.status = True
            else:
                _LOGGER.debug("AC is already on, skipping turn_on command")
                return
        elif command_key == "turn_off":
            if self.data.status:
                msg = message.toggle_ac_on_off(target_id)
                _LOGGER.debug("AC is on, queueing turn_off command")
                self.data.status = False
            else:
                _LOGGER.debug("AC is already off, skipping turn_off command")
                return
        elif command_key == "toggle_zone":
            msg = message.toggle_zone(target_id)
        else:
            _LOGGER.error("Unknown command type: %s", command_key)
            return

        if msg:
            await self._command_queue.put((msg, command_key, target_id, value))
            self._ensure_command_queue_worker()
            _LOGGER.debug(
                "Queued %s command for AirTouch target %s with value %s",
                command_key,
                target_id,
                value,
            )

    def _ensure_command_queue_worker(self) -> None:
        """Start the command queue worker if it is not already running."""
        if self._command_queue_task is not None and not self._command_queue_task.done():
            return

        self._command_queue_task = self._entry.async_create_background_task(
            self.hass,
            self._async_command_queue_worker(),
            f"{DOMAIN} command queue",
        )

    async def _async_command_queue_worker(self) -> None:
        """Send queued commands at a fixed interval."""
        try:
            while True:
                try:
                    (
                        msg,
                        command_type,
                        target_id,
                        value,
                    ) = await self._command_queue.get()
                except asyncio.CancelledError:
                    return

                try:
                    await self._async_send_queued_command(
                        msg,
                        command_type,
                        target_id,
                        value,
                    )
                finally:
                    self._command_queue.task_done()

                await asyncio.sleep(self._command_queue_interval)
        except asyncio.CancelledError:
            return

    async def _async_shutdown(self, _event: object) -> None:
        """Cancel background tasks and close the socket on shutdown."""
        if self._command_queue_task and not self._command_queue_task.done():
            self._command_queue_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._command_queue_task
        if self.socket_writer:
            self.socket_writer.close()
            with contextlib.suppress(OSError):
                await self.socket_writer.wait_closed()
            self.connected = False

    async def _async_send_queued_command(
        self, msg: bytearray, command_type: str, target_id: int, value: Any
    ) -> None:
        """Send a queued command to the AirTouch unit."""
        async with self._socket_lock:
            try:
                if not self.connected:
                    await self.connect_to_airtouch()

                if self.socket_writer is None:
                    _LOGGER.error("Connection to AirTouch failed")
                    self.connected = False
                    return

                self.socket_writer.write(msg)
                async with asyncio.timeout(RESPONSE_TIMEOUT):
                    await self.socket_writer.drain()
                _LOGGER.debug(
                    "Sent %s command to AirTouch for target %s with value %s",
                    command_type,
                    target_id,
                    value,
                )
            except (UpdateFailed, TimeoutError, OSError) as e:
                _LOGGER.error("Failed to send command to AirTouch: %s", e)
                self.connected = False
            finally:
                if self.socket_writer:
                    self.socket_writer.close()
                    with contextlib.suppress(OSError):
                        await self.socket_writer.wait_closed()
                    self.connected = False

    async def adjust_temperature(self, zone_id: int, target_temp: int) -> None:
        """Adjust temperature by sending repeated set_fan commands based on current target."""
        current_target = self.data.group_target_temperatures.get(zone_id)
        if current_target is None:
            _LOGGER.error("Current target temperature for zone %s not found", zone_id)
            return

        diff = target_temp - current_target
        inc_dec = 1 if diff > 0 else -1
        num_steps = abs(int(diff))

        _LOGGER.debug(
            "Adjusting temperature for zone %s from %s to %s with %s steps",
            zone_id,
            current_target,
            target_temp,
            num_steps,
        )

        for _ in range(num_steps):
            await asyncio.sleep(1)  # small delay between commands
            await self.send_command("set_group_temperature", zone_id, inc_dec)
            _LOGGER.debug("Adjusting temperature by %s for zone %s", inc_dec, zone_id)

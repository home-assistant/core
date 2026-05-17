"""Coordinator module for the AirTouch 3 integration."""

import asyncio
import contextlib
import logging
from typing import Any

from pyairtouch3 import DEFAULT_PORT, Aircon, AirTouchClient, AirTouchError

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

COMMAND_QUEUE_INTERVAL = 5
QUEUED_VALUE_COMMANDS = {"set_mode", "set_fan_speed", "set_group_temperature"}


async def async_fetch_airtouch_data(host: str, port: int = DEFAULT_PORT) -> Aircon:
    """Fetch and parse data from an AirTouch 3 controller."""
    try:
        return await AirTouchClient(host, port, logger=_LOGGER).fetch_aircon()
    except AirTouchError as err:
        _LOGGER.debug("AirTouch 3 communication with %s:%s failed: %s", host, port, err)
        raise UpdateFailed(str(err)) from err


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
        self._client = AirTouchClient(host, port, logger=_LOGGER)
        self._socket_lock = asyncio.Lock()
        self._command_queue: asyncio.Queue[tuple[str, int, Any]] = asyncio.Queue()
        self._command_queue_interval = COMMAND_QUEUE_INTERVAL
        self._command_queue_task: asyncio.Task[None] | None = None
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)

    @property
    def system_id(self) -> str:
        """Return a stable controller identifier for entity unique IDs."""
        return self._entry.unique_id or self.host

    async def _async_update_data(self) -> Aircon:
        """Fetch data from AirTouch."""
        async with self._socket_lock:
            return await async_fetch_airtouch_data(self.host, self.port)

    async def send_command(
        self, command_type: str, target_id: int, value: Any = None
    ) -> None:
        """Send a command to the AirTouch unit."""
        command_key = command_type
        if hasattr(command_key, "value"):
            command_key = command_key.value
        if not isinstance(command_key, str):
            command_key = str(command_key)

        if command_key == "turn_on":
            if not self.data.status:
                _LOGGER.debug("AC is off, queueing turn_on command")
                self.data.status = True
            else:
                _LOGGER.debug("AC is already on, skipping turn_on command")
                return
        elif command_key == "turn_off":
            if self.data.status:
                _LOGGER.debug("AC is on, queueing turn_off command")
                self.data.status = False
            else:
                _LOGGER.debug("AC is already off, skipping turn_off command")
                return
        elif command_key != "toggle_zone" and command_key not in QUEUED_VALUE_COMMANDS:
            _LOGGER.error("Unknown command type: %s", command_key)
            return

        await self._command_queue.put((command_key, target_id, value))
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
                        command_type,
                        target_id,
                        value,
                    ) = await self._command_queue.get()
                except asyncio.CancelledError:
                    return

                try:
                    await self._async_send_queued_command(
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
        """Cancel background command tasks on shutdown."""
        if self._command_queue_task and not self._command_queue_task.done():
            self._command_queue_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._command_queue_task

    async def _async_send_queued_command(
        self, command_type: str, target_id: int, value: Any
    ) -> None:
        """Send a queued command to the AirTouch unit."""
        async with self._socket_lock:
            try:
                if command_type == "set_mode":
                    await self._client.set_mode(target_id, self.data.brand_id, value)
                elif command_type == "set_fan_speed":
                    await self._client.set_fan_speed(
                        target_id, self.data.brand_id, value
                    )
                elif command_type == "set_group_temperature":
                    await self._client.adjust_zone_temperature(target_id, value)
                elif command_type in {"turn_on", "turn_off"}:
                    await self._client.toggle_ac_power(target_id)
                elif command_type == "toggle_zone":
                    await self._client.toggle_zone(target_id)
                else:
                    _LOGGER.error("Unknown queued AirTouch command: %s", command_type)
                    return

                _LOGGER.debug(
                    "Sent %s command to AirTouch for target %s with value %s",
                    command_type,
                    target_id,
                    value,
                )
            except AirTouchError as err:
                _LOGGER.error("Failed to send command to AirTouch: %s", err)

    async def adjust_temperature(self, zone_id: int, target_temp: int) -> None:
        """Adjust temperature by sending repeated set_fan commands based on current target."""
        zone = next((zone for zone in self.data.zones if zone.id == zone_id), None)
        if zone is None:
            _LOGGER.error("Current target temperature for zone %s not found", zone_id)
            return

        current_target = zone.desired_temperature
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

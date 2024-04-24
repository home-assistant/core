"""UniFi Network entity helper."""

from __future__ import annotations

from datetime import datetime, timedelta

import aiounifi
from aiounifi.models.device import DeviceSetPoePortModeRequest

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
import homeassistant.util.dt as dt_util


class UnifiEntityHelper:
    """UniFi Network integration handling platforms for entity registration."""

    def __init__(self, hass: HomeAssistant, api: aiounifi.Controller) -> None:
        """Initialize the UniFi entity loader."""
        self.hass = hass
        self.api = api

        self._device_command = UnifiDeviceCommand(hass, api)
        self._heartbeat = UnifiEntityHeartbeat(hass)

    @callback
    def reset(self) -> None:
        """Cancel timers."""
        self._device_command.reset()
        self._heartbeat.reset()

    @callback
    def initialize(self) -> None:
        """Initialize entity helper."""
        self._heartbeat.initialize()

    @property
    def signal_heartbeat(self) -> str:
        """Event to signal new heartbeat missed."""
        return self._heartbeat.signal

    @callback
    def update_heartbeat(self, unique_id: str, heartbeat_expire_time: datetime) -> None:
        """Update device time in heartbeat monitor."""
        self._heartbeat.update(unique_id, heartbeat_expire_time)

    @callback
    def remove_heartbeat(self, unique_id: str) -> None:
        """Update device time in heartbeat monitor."""
        self._heartbeat.remove(unique_id)

    @callback
    def queue_poe_port_command(
        self, device_id: str, port_idx: int, poe_mode: str
    ) -> None:
        """Queue commands to execute them together per device."""
        self._device_command.queue_poe_command(device_id, port_idx, poe_mode)


class UnifiEntityHeartbeat:
    """UniFi entity heartbeat monitor."""

    CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the heartbeat monitor."""
        self.hass = hass

        self._cancel_heartbeat_check: CALLBACK_TYPE | None = None
        self._heartbeat_time: dict[str, datetime] = {}

    @callback
    def reset(self) -> None:
        """Cancel timers."""
        if self._cancel_heartbeat_check:
            self._cancel_heartbeat_check()
            self._cancel_heartbeat_check = None

    @callback
    def initialize(self) -> None:
        """Initialize heartbeat monitor."""
        self._cancel_heartbeat_check = async_track_time_interval(
            self.hass, self._check_for_stale, self.CHECK_HEARTBEAT_INTERVAL
        )

    @property
    def signal(self) -> str:
        """Event to signal new heartbeat missed."""
        return "unifi-heartbeat-missed"

    @callback
    def update(self, unique_id: str, heartbeat_expire_time: datetime) -> None:
        """Update device time in heartbeat monitor."""
        self._heartbeat_time[unique_id] = heartbeat_expire_time

    @callback
    def remove(self, unique_id: str) -> None:
        """Remove device from heartbeat monitor."""
        self._heartbeat_time.pop(unique_id, None)

    @callback
    def _check_for_stale(self, *_: datetime) -> None:
        """Check for any devices scheduled to be marked disconnected."""
        now = dt_util.utcnow()

        unique_ids_to_remove = []
        for unique_id, heartbeat_expire_time in self._heartbeat_time.items():
            if now > heartbeat_expire_time:
                async_dispatcher_send(self.hass, f"{self.signal}_{unique_id}")
                unique_ids_to_remove.append(unique_id)

        for unique_id in unique_ids_to_remove:
            del self._heartbeat_time[unique_id]


class UnifiDeviceCommand:
    """UniFi Device command helper class."""

    COMMAND_DELAY = 5

    def __init__(self, hass: HomeAssistant, api: aiounifi.Controller) -> None:
        """Initialize device command helper."""
        self.hass = hass
        self.api = api

        self._command_queue: dict[str, dict[int, str]] = {}
        self._cancel_command: CALLBACK_TYPE | None = None

    @callback
    def reset(self) -> None:
        """Cancel timers."""
        if self._cancel_command:
            self._cancel_command()
            self._cancel_command = None

    @callback
    def queue_poe_command(self, device_id: str, port_idx: int, poe_mode: str) -> None:
        """Queue commands to execute them together per device."""
        self.reset()

        device_queue = self._command_queue.setdefault(device_id, {})
        device_queue[port_idx] = poe_mode

        async def _command(now: datetime) -> None:
            """Execute previously queued commands."""
            queue = self._command_queue.copy()
            self._command_queue.clear()
            for device_id, device_commands in queue.items():
                device = self.api.devices[device_id]
                commands = list(device_commands.items())
                await self.api.request(
                    DeviceSetPoePortModeRequest.create(device, targets=commands)
                )

        self._cancel_command = async_call_later(self.hass, self.COMMAND_DELAY, _command)

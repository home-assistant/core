"""UniFi Network entity helper."""
from __future__ import annotations

from datetime import datetime, timedelta

import aiounifi
from aiounifi.models.device import DeviceSetPoePortModeRequest

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
import homeassistant.util.dt as dt_util

CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)


class UnifiEntityHelper:
    """UniFi Network integration handling platforms for entity registration."""

    def __init__(self, hass: HomeAssistant, api: aiounifi.Controller) -> None:
        """Initialize the UniFi entity loader."""
        self.hass = hass
        self.api = api

        self._cancel_heartbeat_check: CALLBACK_TYPE | None = None
        self._heartbeat_time: dict[str, datetime] = {}

        self.poe_command_queue: dict[str, dict[int, str]] = {}
        self._cancel_poe_command: CALLBACK_TYPE | None = None

    @callback
    def reset(self) -> None:
        """Cancel timers."""
        if self._cancel_heartbeat_check:
            self._cancel_heartbeat_check()
            self._cancel_heartbeat_check = None

        if self._cancel_poe_command:
            self._cancel_poe_command()
            self._cancel_poe_command = None

    @callback
    def initialize(self) -> None:
        """Initialize entity helper."""
        self._cancel_heartbeat_check = async_track_time_interval(
            self.hass, self._check_for_stale, CHECK_HEARTBEAT_INTERVAL
        )

    @property
    def signal_heartbeat_missed(self) -> str:
        """Event specific per UniFi device tracker to signal new heartbeat missed."""
        return "unifi-heartbeat-missed"

    @callback
    def heartbeat(
        self, unique_id: str, heartbeat_expire_time: datetime | None = None
    ) -> None:
        """Signal when a device has fresh home state."""
        if heartbeat_expire_time is not None:
            self._heartbeat_time[unique_id] = heartbeat_expire_time
            return

        if unique_id in self._heartbeat_time:
            del self._heartbeat_time[unique_id]

    @callback
    def _check_for_stale(self, *_: datetime) -> None:
        """Check for any devices scheduled to be marked disconnected."""
        now = dt_util.utcnow()

        unique_ids_to_remove = []
        for unique_id, heartbeat_expire_time in self._heartbeat_time.items():
            if now > heartbeat_expire_time:
                async_dispatcher_send(
                    self.hass, f"{self.signal_heartbeat_missed}_{unique_id}"
                )
                unique_ids_to_remove.append(unique_id)

        for unique_id in unique_ids_to_remove:
            del self._heartbeat_time[unique_id]

    @callback
    def queue_poe_port_command(
        self, device_id: str, port_idx: int, poe_mode: str
    ) -> None:
        """Queue commands to execute them together per device."""
        if self._cancel_poe_command:
            self._cancel_poe_command()
            self._cancel_poe_command = None

        device_queue = self.poe_command_queue.setdefault(device_id, {})
        device_queue[port_idx] = poe_mode

        async def _execute_command(now: datetime) -> None:
            """Execute previously queued commands."""
            queue = self.poe_command_queue.copy()
            self.poe_command_queue.clear()
            for device_id, device_commands in queue.items():
                device = self.api.devices[device_id]
                commands = list(device_commands.items())
                await self.api.request(
                    DeviceSetPoePortModeRequest.create(device, targets=commands)
                )

        self._cancel_poe_command = async_call_later(self.hass, 5, _execute_command)

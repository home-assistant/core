"""UniFi Network entity helper."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, cast

import aiounifi
from aiounifi.interfaces.api_handlers import APIHandler
from aiounifi.models.api import ApiItem
from aiounifi.models.device import DeviceSetPoePortModeRequest
from aiounifi.models.firewall_policy import FirewallPolicy, FirewallPolicySchedule

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util


class UnifiEntityHelper:
    """UniFi Network integration handling platforms for entity registration."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: aiounifi.Controller,
        write_lock: Callable[[APIHandler[Any]], asyncio.Lock],
    ) -> None:
        """Initialize the UniFi entity loader.

        write_lock returns the lock a handler's fetches hold.
        """
        self.hass = hass
        self.api = api

        self._device_command = UnifiDeviceCommand(hass, api)
        self._object_command = UnifiObjectCommand(write_lock)
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

    async def save_firewall_policy(
        self,
        obj_id: str,
        *,
        enabled: bool | None = None,
        schedule_fn: Callable[[Mapping[str, Any]], FirewallPolicySchedule | None]
        | None = None,
    ) -> None:
        """Save a change to a firewall policy.

        schedule_fn builds the new schedule from the current one, or returns
        None when the current one needs no change.
        """
        policies = self.api.firewall_policies

        async def save(policy: FirewallPolicy) -> None:
            schedule = None
            if schedule_fn is not None:
                schedule = schedule_fn(policy.schedule or {})
                if schedule is None and enabled is None:
                    return
            response = await policies.save(policy, enabled=enabled, schedule=schedule)
            if not response.get("data"):
                # The controller accepted the change without sending the policy
                # back. Cache what was sent, so the next write builds on it.
                saved = cast(dict[str, Any], deepcopy(policy.raw))
                if enabled is not None:
                    saved["enabled"] = enabled
                if schedule is not None:
                    saved["schedule"] = schedule
                policies.process_raw([saved])

        await self._object_command.write(policies, obj_id, save)


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
            for dev_id, device_commands in queue.items():
                device = self.api.devices[dev_id]
                commands = list(device_commands.items())
                await self.api.request(
                    DeviceSetPoePortModeRequest.create(device, targets=commands)
                )

        self._cancel_command = async_call_later(self.hass, self.COMMAND_DELAY, _command)


class UnifiObjectCommand:
    """UniFi object command helper class.

    Some writes send a whole object built from its cached copy. Writes to a
    handler's objects run one at a time, each starting from the object as the
    one before it left it. They hold the lock the handler's fetches hold, so a
    fetch can't answer between writes with an object from before them.

    Unlike PoE commands these aren't delayed and batched: the caller needs
    to know whether its own change was accepted.
    """

    def __init__(self, write_lock: Callable[[APIHandler[Any]], asyncio.Lock]) -> None:
        """Initialize object command helper."""
        self._write_lock = write_lock

    async def write[ItemT: ApiItem](
        self,
        handler: APIHandler[ItemT],
        obj_id: str,
        change: Callable[[ItemT], Awaitable[None]],
    ) -> None:
        """Apply a change to an object, starting from its latest cached copy."""
        async with self._write_lock(handler):
            await change(handler[obj_id])

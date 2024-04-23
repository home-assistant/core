"""UniFi Network abstraction."""

from __future__ import annotations

from datetime import datetime, timedelta

import aiounifi
from aiounifi.models.device import DeviceSetPoePortModeRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
import homeassistant.util.dt as dt_util

from ..const import ATTR_MANUFACTURER, CONF_SITE_ID, DOMAIN as UNIFI_DOMAIN, PLATFORMS
from .config import UnifiConfig
from .entity_loader import UnifiEntityLoader
from .websocket import UnifiWebsocket

CHECK_HEARTBEAT_INTERVAL = timedelta(seconds=1)


class UnifiHub:
    """Manages a single UniFi Network instance."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: aiounifi.Controller
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.api = api
        self.config = UnifiConfig.from_config_entry(config_entry)
        self.entity_loader = UnifiEntityLoader(self)
        self.websocket = UnifiWebsocket(hass, api, self.signal_reachable)

        self.site = config_entry.data[CONF_SITE_ID]
        self.is_admin = False

        self._cancel_heartbeat_check: CALLBACK_TYPE | None = None
        self._heartbeat_time: dict[str, datetime] = {}

        self.poe_command_queue: dict[str, dict[int, str]] = {}
        self._cancel_poe_command: CALLBACK_TYPE | None = None

    @callback
    @staticmethod
    def get_hub(hass: HomeAssistant, config_entry: ConfigEntry) -> UnifiHub:
        """Get UniFi hub from config entry."""
        hub: UnifiHub = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
        return hub

    @property
    def available(self) -> bool:
        """Websocket connection state."""
        return self.websocket.available

    @property
    def signal_reachable(self) -> str:
        """Integration specific event to signal a change in connection status."""
        return f"unifi-reachable-{self.config.entry.entry_id}"

    @property
    def signal_options_update(self) -> str:
        """Event specific per UniFi entry to signal new options."""
        return f"unifi-options-{self.config.entry.entry_id}"

    @property
    def signal_heartbeat_missed(self) -> str:
        """Event specific per UniFi device tracker to signal new heartbeat missed."""
        return "unifi-heartbeat-missed"

    async def initialize(self) -> None:
        """Set up a UniFi Network instance."""
        await self.entity_loader.initialize()

        assert self.config.entry.unique_id is not None
        self.is_admin = self.api.sites[self.config.entry.unique_id].role == "admin"

        self.config.entry.add_update_listener(self.async_config_entry_updated)

        self._cancel_heartbeat_check = async_track_time_interval(
            self.hass, self._async_check_for_stale, CHECK_HEARTBEAT_INTERVAL
        )

    @callback
    def async_heartbeat(
        self, unique_id: str, heartbeat_expire_time: datetime | None = None
    ) -> None:
        """Signal when a device has fresh home state."""
        if heartbeat_expire_time is not None:
            self._heartbeat_time[unique_id] = heartbeat_expire_time
            return

        if unique_id in self._heartbeat_time:
            del self._heartbeat_time[unique_id]

    @callback
    def _async_check_for_stale(self, *_: datetime) -> None:
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
    def async_queue_poe_port_command(
        self, device_id: str, port_idx: int, poe_mode: str
    ) -> None:
        """Queue commands to execute them together per device."""
        if self._cancel_poe_command:
            self._cancel_poe_command()
            self._cancel_poe_command = None

        device_queue = self.poe_command_queue.setdefault(device_id, {})
        device_queue[port_idx] = poe_mode

        async def async_execute_command(now: datetime) -> None:
            """Execute previously queued commands."""
            queue = self.poe_command_queue.copy()
            self.poe_command_queue.clear()
            for device_id, device_commands in queue.items():
                device = self.api.devices[device_id]
                commands = list(device_commands.items())
                await self.api.request(
                    DeviceSetPoePortModeRequest.create(device, targets=commands)
                )

        self._cancel_poe_command = async_call_later(self.hass, 5, async_execute_command)

    @property
    def device_info(self) -> DeviceInfo:
        """UniFi Network device info."""
        assert self.config.entry.unique_id is not None

        version: str | None = None
        if sysinfo := next(iter(self.api.system_information.values()), None):
            version = sysinfo.version

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(UNIFI_DOMAIN, self.config.entry.unique_id)},
            manufacturer=ATTR_MANUFACTURER,
            model="UniFi Network Application",
            name="UniFi Network",
            sw_version=version,
        )

    @callback
    def async_update_device_registry(self) -> DeviceEntry:
        """Update device registry."""
        device_registry = dr.async_get(self.hass)
        return device_registry.async_get_or_create(
            config_entry_id=self.config.entry.entry_id, **self.device_info
        )

    @staticmethod
    async def async_config_entry_updated(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle signals of config entry being updated.

        If config entry is updated due to reauth flow
        the entry might already have been reset and thus is not available.
        """
        if not (hub := hass.data[UNIFI_DOMAIN].get(config_entry.entry_id)):
            return
        hub.config = UnifiConfig.from_config_entry(config_entry)
        async_dispatcher_send(hass, hub.signal_options_update)

    @callback
    def shutdown(self, event: Event) -> None:
        """Wrap the call to unifi.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.websocket.stop()

    async def async_reset(self) -> bool:
        """Reset this hub to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        await self.websocket.stop_and_wait()

        unload_ok = await self.hass.config_entries.async_unload_platforms(
            self.config.entry, PLATFORMS
        )

        if not unload_ok:
            return False

        if self._cancel_heartbeat_check:
            self._cancel_heartbeat_check()
            self._cancel_heartbeat_check = None

        if self._cancel_poe_command:
            self._cancel_poe_command()
            self._cancel_poe_command = None

        return True

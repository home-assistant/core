"""UniFi Network abstraction."""

from __future__ import annotations

from datetime import datetime

import aiounifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import ATTR_MANUFACTURER, CONF_SITE_ID, DOMAIN as UNIFI_DOMAIN, PLATFORMS
from .config import UnifiConfig
from .entity_helper import UnifiEntityHelper
from .entity_loader import UnifiEntityLoader
from .websocket import UnifiWebsocket


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
        self._entity_helper = UnifiEntityHelper(hass, api)
        self.websocket = UnifiWebsocket(hass, api, self.signal_reachable)

        self.site = config_entry.data[CONF_SITE_ID]
        self.is_admin = False

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
    def signal_heartbeat_missed(self) -> str:
        """Event to signal new heartbeat missed."""
        return self._entity_helper.signal_heartbeat

    @callback
    def update_heartbeat(self, unique_id: str, heartbeat_expire_time: datetime) -> None:
        """Update device time in heartbeat monitor."""
        self._entity_helper.update_heartbeat(unique_id, heartbeat_expire_time)

    @callback
    def remove_heartbeat(self, unique_id: str) -> None:
        """Update device time in heartbeat monitor."""
        self._entity_helper.remove_heartbeat(unique_id)

    @callback
    def queue_poe_port_command(
        self, device_id: str, port_idx: int, poe_mode: str
    ) -> None:
        """Queue commands to execute them together per device."""
        self._entity_helper.queue_poe_port_command(device_id, port_idx, poe_mode)

    @property
    def signal_reachable(self) -> str:
        """Integration specific event to signal a change in connection status."""
        return f"unifi-reachable-{self.config.entry.entry_id}"

    @property
    def signal_options_update(self) -> str:
        """Event specific per UniFi entry to signal new options."""
        return f"unifi-options-{self.config.entry.entry_id}"

    async def initialize(self) -> None:
        """Set up a UniFi Network instance."""
        await self.entity_loader.initialize()
        self._entity_helper.initialize()

        assert self.config.entry.unique_id is not None
        self.is_admin = self.api.sites[self.config.entry.unique_id].role == "admin"

        self.config.entry.add_update_listener(self.async_config_entry_updated)

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

        self._entity_helper.reset()

        return True

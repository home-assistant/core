"""UniFi Network abstraction."""

from datetime import datetime
import re
from typing import TYPE_CHECKING

import aiounifi

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import ATTR_MANUFACTURER, CONF_SITE_ID, DOMAIN, LOGGER, PLATFORMS
from .config import UnifiConfig
from .connection import UnifiConnectionManager
from .entity_helper import UnifiEntityHelper
from .entity_loader import UnifiEntityLoader
from .websocket import UnifiWebsocket

if TYPE_CHECKING:
    from .. import UnifiConfigEntry

OBJECT_ID = re.compile(r"[0-9a-f]{24}")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class UnifiHub:
    """Manages a single UniFi Network instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UnifiConfigEntry,
        api: aiounifi.Controller,
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.api = api
        self.config = UnifiConfig.from_config_entry(config_entry)
        self.connection = UnifiConnectionManager(
            hass,
            config_entry,
            api,
            self.signal_reachable,
            self._async_connection_recovered,
        )
        config_entry.async_on_unload(self.connection.stop)
        self.websocket = UnifiWebsocket(self.connection)
        self.entity_loader = UnifiEntityLoader(self)
        self._entity_helper = UnifiEntityHelper(hass, api)

        self.site = config_entry.data[CONF_SITE_ID]
        self.is_admin = False

    @property
    def available(self) -> bool:
        """Shared UniFi session state."""
        return self.connection.available

    async def _async_connection_recovered(self) -> None:
        """Resync data before push updates resume after app recovery."""
        await self.entity_loader.async_resync()
        if self.available and self.websocket.running:
            self.websocket.start_websocket()

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
        await self.entity_loader.async_load_sites()
        # Requests for a site that is gone get 401, check it before using it
        unique_id = self.config.entry.unique_id
        assert unique_id is not None
        if unique_id not in self.api.sites:
            unique_id = self._async_update_site_unique_id(unique_id)
        if (site := self.api.sites.get(unique_id)) is None:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="site_not_found"
            )
        self.is_admin = site.role == "admin"

        await self.entity_loader.initialize()
        self._entity_helper.initialize()
        self.config.entry.async_on_unload(self._entity_helper.reset)

        self.config.entry.async_on_unload(
            self.config.entry.add_update_listener(self.async_config_entry_updated)
        )

    @callback
    def _async_update_site_unique_id(self, old_id: str) -> str:
        """Move the entry from the ObjectId to the UUID UniFi Network 11 gives sites.

        The site name is kept and is unique per controller.
        """
        if not OBJECT_ID.fullmatch(old_id):
            return old_id
        site_ids = {site.name: site.site_id for site in self.api.sites.values()}
        new_id = site_ids.get(self.site)
        if new_id is None or not UUID.fullmatch(new_id):
            return old_id
        if self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, new_id):
            return old_id

        LOGGER.info("UniFi site %s changed ID from %s to %s", self.site, old_id, new_id)
        device_registry = dr.async_get(self.hass)
        for domain in (DOMAIN, SWITCH_DOMAIN):
            device = device_registry.async_get_device_by_identifier(
                (domain, old_id), self.config.entry.entry_id
            )
            if device:
                device_registry.async_update_device(
                    device.id, new_identifiers={(domain, new_id)}
                )
        self.hass.config_entries.async_update_entry(self.config.entry, unique_id=new_id)
        return new_id

    @property
    def device_info(self) -> DeviceInfo:
        """UniFi Network device info."""
        assert self.config.entry.unique_id is not None

        version: str | None = None
        if sysinfo := next(iter(self.api.system_information.values()), None):
            version = sysinfo.version

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.config.entry.unique_id)},
            manufacturer=ATTR_MANUFACTURER,
            model="UniFi Network Application",
            name="UniFi Network",
            sw_version=version,
        )

    @callback
    def async_update_device_registry(self) -> DeviceEntry:
        """Update device registry."""
        device_registry = dr.async_get(self.hass)
        return device_registry.async_get_or_create_from_info(
            config_entry_id=self.config.entry.entry_id, device_info=self.device_info
        )

    @staticmethod
    async def async_config_entry_updated(
        hass: HomeAssistant, config_entry: UnifiConfigEntry
    ) -> None:
        """Apply updated options to the hub.

        Config flows reload the entry after they change its data.
        """
        hub = config_entry.runtime_data
        hub.config = UnifiConfig.from_config_entry(config_entry)
        async_dispatcher_send(hass, hub.signal_options_update)

    @callback
    def shutdown(self, event: Event) -> None:
        """Wrap the call to unifi.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.connection.stop()
        self.websocket.stop()

    async def async_reset(self) -> bool:
        """Reset this hub to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        await self.connection.stop_and_wait()
        await self.websocket.stop_and_wait()

        return await self.hass.config_entries.async_unload_platforms(
            self.config.entry, PLATFORMS
        )

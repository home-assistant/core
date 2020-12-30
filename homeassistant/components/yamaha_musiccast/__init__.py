"""The MusicCast integration."""
import abc
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MASTER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    BRAND,
    DOMAIN,
    JOIN_SERVICE_SCHEMA,
    SERVICE_JOIN,
    SERVICE_UNJOIN,
    UNJOIN_SERVICE_SCHEMA,
)
from .musiccast_device import MusicCastData, MusicCastDevice

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["media_player"]

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the MusicCast component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up MusicCast from a config entry."""

    client = MusicCastDevice(hass, async_get_clientsession(hass), entry.data[CONF_HOST])
    coordinator = MusicCastDataUpdateCoordinator(hass, client=client)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    @service.verify_domain_control(hass, DOMAIN)
    async def async_service_handle(service_call: ServiceCall):
        """Handle services."""
        entity_ids = service_call.data.get("entity_id", [])
        if not entity_ids:
            return

        all_entities = list()
        for coord in hass.data[DOMAIN].values():
            all_entities += coord.entities

        entities = [entity for entity in all_entities if entity.entity_id in entity_ids]

        if service_call.service == SERVICE_JOIN:
            master_id = service_call.data[ATTR_MASTER]
            master = next(
                (entity for entity in all_entities if entity.entity_id == master_id),
                None,
            )
            if master and isinstance(master, MusicCastDeviceEntity):
                await master.async_server_join(entities)
            else:
                _LOGGER.error(
                    "Invalid master specified for join service: %s",
                    service_call.data[ATTR_MASTER],
                )
        elif service_call.service == SERVICE_UNJOIN:
            for entity in entities:
                if isinstance(entity, MusicCastDeviceEntity):
                    await entity.async_unjoin()
                else:
                    _LOGGER.error(
                        "Invalid entity specified for unjoin service: %s",
                        entity,
                    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_JOIN,
        async_service_handle,
        JOIN_SERVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UNJOIN,
        async_service_handle,
        UNJOIN_SERVICE_SCHEMA,
    )

    for component in PLATFORMS:
        coordinator.platforms.append(component)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    entry.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class MusicCastDataUpdateCoordinator(DataUpdateCoordinator[MusicCastData]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: MusicCastDevice) -> None:
        """Initialize."""
        self.musiccast = client
        self.platforms = []
        self.entities = []

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> MusicCastData:
        """Update data via library."""
        try:
            await self.musiccast.fetch()
            return self.musiccast.data
        except Exception as exception:
            print(exception)
            raise UpdateFailed() from exception


class MusicCastEntity(CoordinatorEntity):
    """Defines a base MusicCast entity."""

    def __init__(
        self,
        *,
        entry_id: str,
        coordinator: MusicCastDataUpdateCoordinator,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the MusicCast entity."""
        super().__init__(coordinator)
        self._enabled_default = enabled_default
        self._entry_id = entry_id
        self._icon = icon
        self._name = name
        self._unsub_dispatcher = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default


class MusicCastDeviceEntity(MusicCastEntity, abc.ABC):
    """Defines a MusicCast device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this MusicCast device."""
        return {
            ATTR_IDENTIFIERS: {
                (
                    DOMAIN,
                    "".join(self.coordinator.data.mac_addresses.values()),
                )
            },
            ATTR_NAME: self.coordinator.data.network_name,
            ATTR_MANUFACTURER: BRAND,
            ATTR_MODEL: self.coordinator.data.model_name,
            ATTR_SOFTWARE_VERSION: self.coordinator.data.system_version,
        }

    async def async_server_join(self, entities):
        """Let a server assign all given entities to its group."""
        raise NotImplementedError

    async def async_unjoin(self):
        """Let the device leave a group."""
        raise NotImplementedError

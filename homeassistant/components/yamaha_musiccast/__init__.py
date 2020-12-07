"""The MusicCast integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from pyamaha import AsyncDevice, System
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    BRAND,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["media_player"]

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the MusicCast component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up MusicCast from a config entry."""

    client = AsyncDevice(async_get_clientsession(hass), entry.data[CONF_HOST])

    coordinator = MusicCastDataUpdateCoordinator(hass, client=client)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

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


class MusicCastDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: AsyncDevice) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        try:

            network_status = await self.api.request(System.get_network_status())
            device_info = await self.api.request(System.get_device_info())

            return {
                "network_status": await network_status.json(),
                "device_info": await device_info.json(),
            }
        except Exception as exception:
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


class MusicCastDeviceEntity(MusicCastEntity):
    """Defines a MusicCast device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this MusicCast device."""
        return {
            ATTR_IDENTIFIERS: {
                (
                    DOMAIN,
                    "".join(
                        self.coordinator.data.get("network_status")
                        .get("mac_address")
                        .values()
                    ),
                )
            },
            ATTR_NAME: self.coordinator.data.get("network_status").get(
                "network_name", "Unknown"
            ),
            ATTR_MANUFACTURER: BRAND,
            ATTR_MODEL: self.coordinator.data.get("device_info").get("model_name"),
            ATTR_SOFTWARE_VERSION: self.coordinator.data.get("device_info").get(
                "system_version"
            ),
        }

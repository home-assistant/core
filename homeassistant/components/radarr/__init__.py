"""The Radarr component."""
from __future__ import annotations

from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.models.radarr import RadarrSystemStatus
from aiopyarr.radarr_client import RadarrClient

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    DEFAULT_NAME,
    DEFAULT_UPCOMING_DAYS,
    DOMAIN,
)
from .coordinator import RadarrDataUpdateCoordinator

PLATFORMS = [SENSOR_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Radarr from a config entry."""
    if not entry.options:
        options = {
            CONF_UPCOMING_DAYS: entry.data.get(
                CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
            ),
        }
        hass.config_entries.async_update_entry(entry, options=options)
    host_configuration = PyArrHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        base_api_path=entry.data[CONF_BASE_PATH],
        ipaddress=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        ssl=entry.data[CONF_SSL],
    )
    api_client = RadarrClient(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
    )
    coordinator = RadarrDataUpdateCoordinator(hass, host_configuration, api_client)
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class RadarrEntity(CoordinatorEntity):
    """Defines a base Radarr entity."""

    def __init__(
        self,
        coordinator: RadarrDataUpdateCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the Radarr entity."""
        super().__init__(coordinator)
        assert isinstance(coordinator.system_status, RadarrSystemStatus)
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.host_configuration.base_url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
            sw_version=coordinator.system_status.version,
        )

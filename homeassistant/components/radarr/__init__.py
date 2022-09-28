"""The Radarr component."""
from __future__ import annotations

from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_SW_VERSION,
    CONF_API_KEY,
    CONF_PLATFORM,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import (
    DiskSpaceDataUpdateCoordinator,
    HealthDataUpdateCoordinator,
    MoviesDataUpdateCoordinator,
    RadarrDataUpdateCoordinator,
    StatusDataUpdateCoordinator,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Steam integration."""
    if SENSOR_DOMAIN not in config:
        return True

    for entry in config[SENSOR_DOMAIN]:
        if entry[CONF_PLATFORM] == DOMAIN:
            async_create_issue(
                hass,
                DOMAIN,
                "deprecated_yaml",
                breaks_in_ha_version="2022.10.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Radarr from a config entry."""
    host_configuration = PyArrHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        url=entry.data[CONF_URL],
    )
    radarr = RadarrClient(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
    )
    coordinators: dict[str, RadarrDataUpdateCoordinator] = {
        "status": StatusDataUpdateCoordinator(hass, host_configuration, radarr),
        "disk_space": DiskSpaceDataUpdateCoordinator(hass, host_configuration, radarr),
        "health": HealthDataUpdateCoordinator(hass, host_configuration, radarr),
        "movie": MoviesDataUpdateCoordinator(hass, host_configuration, radarr),
    }
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class RadarrEntity(CoordinatorEntity[RadarrDataUpdateCoordinator]):
    """Defines a base Radarr entity."""

    _attr_has_entity_name = True
    coordinator: RadarrDataUpdateCoordinator

    def __init__(
        self,
        coordinator: RadarrDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Create Radarr entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the Radarr instance."""
        device_info = DeviceInfo(
            configuration_url=self.coordinator.host_configuration.url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=self.coordinator.config_entry.title,
        )
        if isinstance(self.coordinator, StatusDataUpdateCoordinator):
            device_info[ATTR_SW_VERSION] = self.coordinator.data.version
        return device_info

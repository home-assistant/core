"""The Tautulli integration."""
from __future__ import annotations

from pytautulli import PyTautulli, PyTautulliHostConfiguration

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SSL, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import TautulliDataUpdateCoordinator

PLATFORMS = [SENSOR_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tautulli from a config entry."""
    host_configuration = PyTautulliHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        url=entry.data[CONF_URL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        ssl=entry.data[CONF_SSL],
    )
    api_client = PyTautulli(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
    )
    coordinator = TautulliDataUpdateCoordinator(hass, host_configuration, api_client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class TautulliEntity(CoordinatorEntity):
    """Defines a base Tautulli entity."""

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        description: SensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the Tautulli entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}/{description.name}"
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.host_configuration.base_url,
            entry_type="service",
            identifiers={(DOMAIN, entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )

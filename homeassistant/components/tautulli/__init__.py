"""The Tautulli integration."""
from __future__ import annotations

from pytautulli import PyTautulli

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SSL, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MONITORED_USERS, DATA_KEY_COORDINATOR, DEFAULT_NAME, DOMAIN
from .coordinator import TautulliDataUpdateCoordinator

PLATFORMS = [SENSOR_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tautulli from a config entry."""
    api_client = PyTautulli(
        api_token=entry.data[CONF_API_KEY],
        url=entry.data[CONF_URL],
        session=async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        ssl=entry.data[CONF_SSL],
    )
    cordnator = TautulliDataUpdateCoordinator(hass, api_client)
    await cordnator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_KEY_COORDINATOR: cordnator}
    if not entry.options:
        options = {CONF_MONITORED_USERS: entry.data.get(CONF_MONITORED_USERS)}
        hass.config_entries.async_update_entry(entry, options=options)

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

    coordinator: TautulliDataUpdateCoordinator

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        name: str,
        server_unique_id: str,
    ) -> None:
        """Initialize the Tautulli entity."""
        super().__init__(coordinator)
        self._attr_name = name
        self._server_unique_id = server_unique_id
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.api_client._host.base_url,
            entry_type="service",
            identifiers={(DOMAIN, server_unique_id)},
            manufacturer=DEFAULT_NAME,
            name=name,
        )

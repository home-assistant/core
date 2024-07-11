"""The Tautulli integration."""

from __future__ import annotations

from pytautulli import PyTautulli, PyTautulliApiUser, PyTautulliHostConfiguration

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import TautulliDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]
type TautulliConfigEntry = ConfigEntry[TautulliDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TautulliConfigEntry) -> bool:
    """Set up Tautulli from a config entry."""
    host_configuration = PyTautulliHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        url=entry.data[CONF_URL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    api_client = PyTautulli(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
    )
    entry.runtime_data = TautulliDataUpdateCoordinator(
        hass, host_configuration, api_client
    )
    await entry.runtime_data.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TautulliConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class TautulliEntity(CoordinatorEntity[TautulliDataUpdateCoordinator]):
    """Defines a base Tautulli entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        description: EntityDescription,
        user: PyTautulliApiUser | None = None,
    ) -> None:
        """Initialize the Tautulli entity."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_description = description
        self.user = user
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.host_configuration.base_url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, user.user_id if user else entry_id)},
            manufacturer=DEFAULT_NAME,
            name=user.username if user else DEFAULT_NAME,
        )

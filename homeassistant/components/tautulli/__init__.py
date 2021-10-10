"""The Tautulli integration."""
from __future__ import annotations

from pytautulli import PyTautulli, exceptions

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_NAME,
    CONF_API_KEY,
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MONITORED_USERS,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import TautulliDataUpdateCoordinator

PLATFORMS = [SENSOR_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tautulli from a config entry."""
    api_client = PyTautulli(
        api_token=entry.data[CONF_API_KEY],
        hostname=entry.data[CONF_HOST],
        session=async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        port=entry.data[CONF_PORT],
        ssl=entry.data[CONF_SSL],
        base_api_path=entry.data[CONF_PATH],
    )
    try:
        await api_client.async_get_activity()
    except exceptions.PyTautulliConnectionException as ex:
        raise ConfigEntryNotReady(ex) from ex
    except (exceptions.PyTautulliAuthenticationException) as ex:
        raise ConfigEntryAuthFailed(ex) from ex

    coordinator = TautulliDataUpdateCoordinator(hass, api_client)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api_client,
        DATA_KEY_COORDINATOR: coordinator,
    }
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

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        name: str,
        server_unique_id: str,
    ) -> None:
        """Initialize the Tautulli entity."""
        super().__init__(coordinator)
        self._server_unique_id = server_unique_id
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the application."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._server_unique_id)},
            ATTR_NAME: "Activity Sensor",
            ATTR_MANUFACTURER: DEFAULT_NAME,
            "entry_type": "service",
        }

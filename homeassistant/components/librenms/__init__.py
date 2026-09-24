"""The LibreNMS integration."""

from aiolibrenms import Librenms
from aiolibrenms.const import CONNECT_ERRORS
from aiolibrenms.exceptions import LibrenmsUnauthenticatedError

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import LibrenmsCentralDataUpdateCoordinator, LibrenmsConfigEntry

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LibrenmsConfigEntry) -> bool:
    """Set up LibreNMS from a config entry."""

    api = Librenms(
        async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
        entry.data[CONF_API_KEY],
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_SSL],
    )

    try:
        await api.system.async_get_system_info()
    except LibrenmsUnauthenticatedError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_error",
        ) from err
    except CONNECT_ERRORS as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    coordinator = LibrenmsCentralDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LibrenmsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

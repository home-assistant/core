"""Support for Hydrawise cloud."""

from pydrawise import auth, client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN, SCAN_INTERVAL
from .coordinator import HydrawiseDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hydrawise from a config entry."""
    if CONF_USERNAME not in config_entry.data or CONF_PASSWORD not in config_entry.data:
        # The GraphQL API requires username and password to authenticate. If either is
        # missing, reauth is required.
        raise ConfigEntryAuthFailed

    hydrawise = client.Hydrawise(
        auth.Auth(config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD])
    )

    coordinator = HydrawiseDataUpdateCoordinator(hass, hydrawise, SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

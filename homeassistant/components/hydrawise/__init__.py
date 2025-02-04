"""Support for Hydrawise cloud."""

from pydrawise import auth, hybrid

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import APP_ID, DOMAIN
from .coordinator import (
    HydrawiseMainDataUpdateCoordinator,
    HydrawiseUpdateCoordinators,
    HydrawiseWaterUseDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]

_REQUIRED_AUTH_KEYS = (CONF_USERNAME, CONF_PASSWORD, CONF_API_KEY)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hydrawise from a config entry."""
    if any(k not in config_entry.data for k in _REQUIRED_AUTH_KEYS):
        # If we are missing any required authentication keys, trigger a reauth flow.
        raise ConfigEntryAuthFailed

    hydrawise = hybrid.HybridClient(
        auth.HybridAuth(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_API_KEY],
        ),
        app_id=APP_ID,
    )

    main_coordinator = HydrawiseMainDataUpdateCoordinator(hass, hydrawise)
    await main_coordinator.async_config_entry_first_refresh()
    water_use_coordinator = HydrawiseWaterUseDataUpdateCoordinator(
        hass, hydrawise, main_coordinator
    )
    await water_use_coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = (
        HydrawiseUpdateCoordinators(
            main=main_coordinator,
            water_use=water_use_coordinator,
        )
    )
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

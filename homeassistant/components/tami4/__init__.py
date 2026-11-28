"""The Tami4Edge integration."""

from Tami4EdgeAPI import Tami4EdgeAPI, exceptions

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import CONF_REFRESH_TOKEN
from .coordinator import Tami4ConfigEntry, Tami4EdgeCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: Tami4ConfigEntry) -> None:
    """Set up tami4 from a config entry."""
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)

    try:
        api = await hass.async_add_executor_job(Tami4EdgeAPI, refresh_token)
    except exceptions.RefreshTokenExpiredException as ex:
        raise ConfigEntryError("API Refresh token expired") from ex
    except exceptions.TokenRefreshFailedException as ex:
        raise ConfigEntryNotReady("Error connecting to API") from ex

    coordinator = Tami4EdgeCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: Tami4ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

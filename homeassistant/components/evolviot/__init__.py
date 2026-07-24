"""EvolvIOT Home Assistant integration."""

from typing import Any

from pyevolviot import (
    EvolvIOTApi,
    EvolvIOTApiError,
    EvolvIOTAuthError,
    normalize_api_base_url,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_API_BASE_URL,
    CONF_REFRESH_TOKEN,
    CONF_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import EvolvIOTDataUpdateCoordinator

type EvolvIOTConfigEntry = ConfigEntry[EvolvIOTDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EvolvIOTConfigEntry) -> bool:
    """Set up EvolvIOT from a config entry."""

    async def async_token_updated(token_data: dict[str, Any]) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: token_data[CONF_ACCESS_TOKEN],
                CONF_REFRESH_TOKEN: token_data.get(CONF_REFRESH_TOKEN, ""),
            },
        )

    verify_ssl = bool(entry.data.get(CONF_VERIFY_SSL, True))
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    api = EvolvIOTApi(
        session,
        normalize_api_base_url(entry.data[CONF_API_BASE_URL]),
        entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        verify_ssl=verify_ssl,
        token_update_callback=async_token_updated,
    )
    coordinator = EvolvIOTDataUpdateCoordinator(hass, api, entry)
    try:
        await coordinator.async_setup()
    except EvolvIOTAuthError as err:
        raise ConfigEntryAuthFailed("Invalid EvolvIOT credentials") from err
    except EvolvIOTApiError as err:
        raise ConfigEntryNotReady("Could not connect to EvolvIOT") from err

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EvolvIOTConfigEntry) -> bool:
    """Unload EvolvIOT config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

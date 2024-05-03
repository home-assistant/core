"""The Discovergy integration."""

from __future__ import annotations

from pydiscovergy import Discovergy
from pydiscovergy.authentication import BasicAuth
import pydiscovergy.error as discovergyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .coordinator import DiscovergyUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

DiscovergyConfigEntry = ConfigEntry[list[DiscovergyUpdateCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: DiscovergyConfigEntry) -> bool:
    """Set up Discovergy from a config entry."""
    client = Discovergy(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        httpx_client=get_async_client(hass),
        authentication=BasicAuth(),
    )

    try:
        # try to get meters from api to check if credentials are still valid and for later use
        # if no exception is raised everything is fine to go
        meters = await client.meters()
    except discovergyError.InvalidLogin as err:
        raise ConfigEntryAuthFailed("Invalid email or password") from err
    except Exception as err:
        raise ConfigEntryNotReady(
            "Unexpected error while while getting meters"
        ) from err

    # Init coordinators for meters
    coordinators = []
    for meter in meters:
        # Create coordinator for meter, set config entry and fetch initial data,
        # so we have data when entities are added
        coordinator = DiscovergyUpdateCoordinator(
            hass=hass,
            meter=meter,
            discovergy_client=client,
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)

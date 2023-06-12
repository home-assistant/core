"""The Discovergy integration."""
from __future__ import annotations

from dataclasses import dataclass

import pydiscovergy
from pydiscovergy.authentication import BasicAuth
import pydiscovergy.error as discovergyError
from pydiscovergy.models import Meter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import APP_NAME, DOMAIN
from .coordinator import DiscovergyUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


@dataclass
class DiscovergyData:
    """Discovergy data class to share meters and api client."""

    api_client: pydiscovergy.Discovergy
    meters: list[Meter]
    coordinators: dict[str, DiscovergyUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discovergy from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # init discovergy data class
    discovergy_data = DiscovergyData(
        api_client=pydiscovergy.Discovergy(
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            app_name=APP_NAME,
            httpx_client=get_async_client(hass),
            authentication=BasicAuth(),
        ),
        meters=[],
        coordinators={},
    )

    try:
        # try to get meters from api to check if credentials are still valid and for later use
        # if no exception is raised everything is fine to go
        discovergy_data.meters = await discovergy_data.api_client.get_meters()
    except discovergyError.InvalidLogin as err:
        raise ConfigEntryAuthFailed("Invalid email or password") from err
    except Exception as err:  # pylint: disable=broad-except
        raise ConfigEntryNotReady(
            "Unexpected error while while getting meters"
        ) from err

    # Init coordinators for meters
    for meter in discovergy_data.meters:
        # Create coordinator for meter, set config entry and fetch initial data,
        # so we have data when entities are added
        coordinator = DiscovergyUpdateCoordinator(
            hass=hass,
            config_entry=entry,
            meter=meter,
            discovergy_client=discovergy_data.api_client,
        )
        await coordinator.async_config_entry_first_refresh()

        discovergy_data.coordinators[meter.get_meter_id()] = coordinator

    hass.data[DOMAIN][entry.entry_id] = discovergy_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)

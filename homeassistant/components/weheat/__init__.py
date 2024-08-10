"""The Weheat integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import DOMAIN
from .coordinator import WeheatDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type WeheatConfigEntry = ConfigEntry[AsyncConfigEntryAuth]


async def async_setup_entry(hass: HomeAssistant, entry: WeheatConfigEntry) -> bool:
    """Set up Weheat from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    entry.runtime_data = api.AsyncConfigEntryAuth(
        async_get_clientsession(hass), session
    )

    hass.data.setdefault(DOMAIN, {})

    coordinator = WeheatDataUpdateCoordinator(
        hass=hass,
        session=session,
        heat_pump=entry.data["heat_pump_info"],
    )
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeheatConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

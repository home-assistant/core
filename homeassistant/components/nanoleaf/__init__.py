"""The Nanoleaf integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from aionanoleaf import EffectsEvent, InvalidToken, Nanoleaf, StateEvent, Unavailable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

PLATFORMS = [Platform.BUTTON, Platform.LIGHT]


@dataclass
class NanoleafEntryData:
    """Class for sharing data within the Nanoleaf integration."""

    device: Nanoleaf
    coordinator: DataUpdateCoordinator
    event_listener: asyncio.Task


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanoleaf from a config entry."""
    nanoleaf = Nanoleaf(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_TOKEN]
    )

    async def async_get_state() -> None:
        """Get the state of the device."""
        try:
            await nanoleaf.get_info()
        except Unavailable as err:
            raise UpdateFailed from err
        except InvalidToken as err:
            raise ConfigEntryAuthFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=entry.title,
        update_interval=timedelta(minutes=1),
        update_method=async_get_state,
    )

    await coordinator.async_config_entry_first_refresh()

    async def update_light_state_callback(event: StateEvent | EffectsEvent) -> None:
        """Receive state and effect event."""
        coordinator.async_set_updated_data(None)

    event_listener = asyncio.create_task(
        nanoleaf.listen_events(
            state_callback=update_light_state_callback,
            effects_callback=update_light_state_callback,
        )
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = NanoleafEntryData(
        nanoleaf, coordinator, event_listener
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    entry_data: NanoleafEntryData = hass.data[DOMAIN].pop(entry.entry_id)
    entry_data.event_listener.cancel()
    return True

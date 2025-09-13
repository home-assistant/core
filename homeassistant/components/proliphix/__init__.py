"""The proliphix component."""

from __future__ import annotations

from proliphix import PDP
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

type ProliphixConfigEntry = ConfigEntry[PDP]

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ProliphixConfigEntry) -> bool:
    """Set up Proliphix from a config entry."""
    pdp = PDP(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    try:
        await hass.async_add_executor_job(pdp.update)
    except requests.exceptions.RequestException as ex:
        raise ConfigEntryNotReady(
            f"Unable to connect to Proliphix thermostat at {entry.data[CONF_HOST]}"
        ) from ex

    # Store the client instance in runtime_data
    entry.runtime_data = pdp

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ProliphixConfigEntry) -> bool:
    """Unload Proliphix config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

"""The Contact Energy NZ integration."""
from __future__ import annotations

from contact_energy_nz import ContactEnergyApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Contact Energy NZ from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    keys = entry.data.keys()
    if "token" in keys:
        connector = ContactEnergyApi.from_token(entry.data[CONF_TOKEN])
    else:
        connector = await ContactEnergyApi.from_credentials(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )

    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_TOKEN: connector.token},
    )

    hass.data[DOMAIN][entry.entry_id] = connector

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

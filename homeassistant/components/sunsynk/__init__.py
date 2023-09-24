"""The Sunsynk integration."""
from __future__ import annotations

from sunsynk.client import SunsynkClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DATA_INVERTER_SN, DOMAIN, SUNSYNK_COORDINATOR
from .coordinator import SunsynkCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sunsynk from a config entry."""
    inverter_sn = entry.data[DATA_INVERTER_SN]

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    inverter_sn = entry.data[DATA_INVERTER_SN]

    api = await SunsynkClient.create(username, password)

    sunsunk_coordinator = SunsynkCoordinator(hass, api, inverter_sn)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_NAME: inverter_sn,
        SUNSYNK_COORDINATOR: sunsunk_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

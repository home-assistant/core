"""The OpenEVSE integration."""

from __future__ import annotations

from openevsehttp.__main__ import OpenEVSE

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

type OpenEVSEConfigEntry = ConfigEntry[OpenEVSE]


async def async_setup_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> bool:
    """Set up openevse from a config entry."""

    entry.runtime_data = OpenEVSE(
        entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    try:
        await entry.runtime_data.test_and_get()
    except TimeoutError as ex:
        raise ConfigEntryError("Unable to connect to charger") from ex

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])

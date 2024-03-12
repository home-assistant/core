"""The godice integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .dice import create_dice

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up godice from a config entry."""

    dice = create_dice(hass, entry)
    try:
        await dice.connect()
    except Exception as err:
        raise ConfigEntryNotReady("Device not found") from err

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = {"device": dice, "device_info": create_devinfo(entry)}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    dev_conn = hass.data[DOMAIN].pop(entry.entry_id)["device"]
    await dev_conn.disconnect()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok


def create_devinfo(conf_entry: ConfigEntry):
    """Set device info displayed in HA."""
    dev_name = conf_entry.data["name"]
    return DeviceInfo(
        identifiers={(DOMAIN, dev_name)},
        name=dev_name,
        manufacturer="Particula",
        model="GoDice",
        sw_version="unknown",
    )

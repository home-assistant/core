"""Energenie Power-Sockets (EGPS) integration."""

from pyegps import PowerStripUSB, get_device
from pyegps.exceptions import MissingLibrary, UsbError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import CONF_DEVICE_API_ID

PLATFORMS = [Platform.SWITCH]

type EnergenieConfigEntry = ConfigEntry[PowerStripUSB]


async def async_migrate_entry(hass: HomeAssistant, entry: EnergenieConfigEntry) -> None:
    """Migrate old config entry."""
    if entry.version == 1:
        new_data = {**entry.data}
        new_data[CONF_DEVICE_API_ID] = new_data.pop("api-device-id")
        hass.config_entries.async_update_entry(entry, data=new_data, version=2)


async def async_setup_entry(hass: HomeAssistant, entry: EnergenieConfigEntry) -> None:
    """Set up Energenie Power Sockets."""
    try:
        powerstrip: PowerStripUSB | None = get_device(entry.data[CONF_DEVICE_API_ID])

    except (MissingLibrary, UsbError) as ex:
        raise ConfigEntryError("Can't access usb devices.") from ex

    if powerstrip is None:
        raise ConfigEntryNotReady(
            "Can't access Energenie Power Sockets, will retry later."
        )

    entry.runtime_data = powerstrip
    entry.async_on_unload(powerstrip.release)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: EnergenieConfigEntry) -> None:
    """Unload config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

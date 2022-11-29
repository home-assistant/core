"""The Home Assistant Sky Connect integration."""
from __future__ import annotations

from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant Sky Connect config entry."""
    matcher = usb.USBCallbackMatcher(
        domain=DOMAIN,
        vid=entry.data["vid"].upper(),
        pid=entry.data["pid"].upper(),
        serial_number=entry.data["serial_number"].lower(),
        manufacturer=entry.data["manufacturer"].lower(),
        description=entry.data["description"].lower(),
    )

    if not usb.async_is_plugged_in(hass, matcher):
        # The USB dongle is not plugged in
        raise ConfigEntryNotReady

    usb_info = usb.UsbServiceInfo(
        device=entry.data["device"],
        vid=entry.data["vid"],
        pid=entry.data["pid"],
        serial_number=entry.data["serial_number"],
        manufacturer=entry.data["manufacturer"],
        description=entry.data["description"],
    )

    await hass.config_entries.flow.async_init(
        "zha",
        context={"source": "usb"},
        data=usb_info,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True

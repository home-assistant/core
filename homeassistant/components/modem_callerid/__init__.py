"""The Modem Caller ID integration."""

from phone_modem import PhoneModem

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DATA_KEY_API, DOMAIN, EXCEPTIONS

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modem Caller ID from a config entry."""
    device = entry.data[CONF_DEVICE]
    api = PhoneModem(device)
    try:
        await api.initialize(device)
    except EXCEPTIONS as ex:
        raise ConfigEntryNotReady(f"Unable to open port: {device}") from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_KEY_API: api}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data[DOMAIN].pop(entry.entry_id)[DATA_KEY_API]
        await api.close()

    return unload_ok

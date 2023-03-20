"""The Obihai integration."""

from socket import gaierror, gethostbyname

from getmac import get_mac_address

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    try:
        ip = gethostbyname(entry.data[CONF_HOST])
    except gaierror as ex:
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.data[CONF_HOST]}"
        ) from ex

    new_unique_id = get_mac_address(ip=ip)
    old_unique_id = entry.unique_id

    if old_unique_id != new_unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=new_unique_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

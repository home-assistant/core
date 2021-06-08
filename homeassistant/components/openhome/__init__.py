"""The openhome component."""


from openhomedevice.device import Device

from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN_DATA_ENTRIES


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the component."""

    hass.data.setdefault(DOMAIN_DATA_ENTRIES, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up openhome from a config entry."""
    entries = hass.data[DOMAIN_DATA_ENTRIES]

    device = await hass.async_add_executor_job(Device, entry.data[CONF_HOST])
    await device.init()

    entries[entry.entry_id] = device

    hass.config_entries.async_setup_platforms(entry, [MEDIA_PLAYER_DOMAIN])

    return True

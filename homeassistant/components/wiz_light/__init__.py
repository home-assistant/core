"""WiZ Light integration."""
import logging

from pywizlight import wizlight
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError

from homeassistant.components.wiz_light.light import WizBulb
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Old way of setting up the wiz_light component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the wiz_light integration from a config entry."""
    ip_address = entry.data.get(CONF_HOST)
    _LOGGER.debug("Get bulb with IP: %s", ip_address)
    try:
        bulb = wizlight(ip_address)
        wizbulb = WizBulb(bulb, entry.data.get(CONF_NAME))
        await wizbulb.get_bulb_type()
        await wizbulb.get_mac()
    except (WizLightTimeOutError, WizLightConnectionError) as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = wizbulb
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # unload wiz_light bulb
    hass.data[DOMAIN].pop(entry.entry_id)
    # Remove config entry
    await hass.config_entries.async_forward_entry_unload(entry, "light")

    return True

"""WiZ Light integration."""
from dataclasses import dataclass
import logging

from pywizlight import BulbType, wizlight
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["light"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the wiz_light integration from a config entry."""
    ip_address = entry.data.get(CONF_HOST)
    _LOGGER.debug("Get bulb with IP: %s", ip_address)
    try:
        bulb = wizlight(ip_address)
        mac_addr = await bulb.getMac()
        bulb_type = await bulb.get_bulbtype()
    except (
        WizLightTimeOutError,
        WizLightConnectionError,
        ConnectionRefusedError,
    ) as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = WizData(
        bulb=bulb, mac_addr=mac_addr, bulb_type=bulb_type
    )
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


@dataclass
class WizData:
    """Data for the wiz integration."""

    bulb: wizlight
    mac_addr: str
    bulb_type: BulbType

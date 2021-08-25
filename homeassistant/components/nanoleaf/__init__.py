"""The Nanoleaf integration."""
from pynanoleaf.pynanoleaf import InvalidToken, Nanoleaf, Unavailable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DEVICE, DOMAIN, NAME, SERIAL_NO
from .util import pynanoleaf_get_info


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanoleaf from a config entry."""
    nanoleaf = Nanoleaf(entry.data[CONF_HOST])
    nanoleaf.token = entry.data[CONF_TOKEN]
    try:
        info = await hass.async_add_executor_job(pynanoleaf_get_info, nanoleaf)
    except Unavailable as err:
        raise ConfigEntryNotReady from err
    except InvalidToken as err:
        raise ConfigEntryAuthFailed from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DEVICE: nanoleaf,
        NAME: info["name"],
        SERIAL_NO: info["serialNo"],
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )
    return True

"""Support for Plum Lightpad devices."""
from copy import deepcopy
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .utils import load_plum

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Plum Lightpad Platform initialization."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    _LOGGER.info("Found Plum Lightpad configuration in config, importing...")
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=deepcopy(conf)
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Plum Lightpad from a config entry."""
    _LOGGER.info("Setting up config entry with ID = %s", entry.unique_id)

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    plum = await load_plum(username, password, hass)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = plum

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, lambda: plum.cleanup())
    return True

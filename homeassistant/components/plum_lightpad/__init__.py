"""Support for Plum Lightpad devices."""
import logging

from aiohttp import ContentTypeError
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .utils import load_plum

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Plum Lightpad Platform initialization."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    _LOGGER.info("Found Plum Lightpad configuration in config, importing")
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plum Lightpad from a config entry."""
    _LOGGER.debug("Setting up config entry with ID = %s", entry.unique_id)

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        plum = await load_plum(username, password, hass)
    except ContentTypeError as ex:
        _LOGGER.error("Unable to authenticate to Plum cloud: %s", ex)
        return False
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Plum cloud: %s", ex)
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = plum

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def cleanup(event):
        """Clean up resources."""
        plum.cleanup()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup))
    return True

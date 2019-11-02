"""Define support for Eufy Security devices."""
from datetime import timedelta
import logging

from eufy_security import async_login
from eufy_security.errors import EufySecurityError, InvalidCredentialsError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import configured_instances
from .const import DATA_API, DATA_LISTENER, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

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


async def async_setup(hass, config):
    """Set up the Eufy Security component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_API] = {}
    hass.data[DOMAIN][DATA_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if conf[CONF_USERNAME] in configured_instances(hass):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: conf[CONF_USERNAME],
                CONF_PASSWORD: conf[CONF_PASSWORD],
            },
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Eufy Security as a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)

    try:
        api = await async_login(
            config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD], session
        )
    except InvalidCredentialsError:
        _LOGGER.error("Invalid username and/or password")
        return False
    except EufySecurityError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady

    hass.data[DOMAIN][DATA_API][config_entry.entry_id] = api

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "camera")
    )

    async def refresh(event_time):
        """Refresh data from the API."""
        _LOGGER.debug("Refreshing API data")
        await api.async_update_device_info()

    hass.data[DOMAIN][DATA_LISTENER][config_entry.entry_id] = async_track_time_interval(
        hass, refresh, DEFAULT_SCAN_INTERVAL
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a Eufy Security config entry."""
    hass.data[DOMAIN][DATA_API].pop(config_entry.entry_id)
    cancel = hass.data[DOMAIN][DATA_LISTENER].pop(config_entry.entry_id)
    cancel()

    await hass.config_entries.async_forward_entry_unload(config_entry, "camera")

    return True

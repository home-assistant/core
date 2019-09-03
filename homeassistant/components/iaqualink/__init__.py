"""Component to embed Aqualink devices."""
import asyncio
import logging

from aiohttp import CookieJar
import voluptuous as vol

from iaqualink import AqualinkClient, AqualinkLoginException, AqualinkThermostat

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

ATTR_CONFIG = "config"
PARALLEL_UPDATES = 0

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


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> None:
    """Set up the Aqualink component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> None:
    """Set up Aqualink from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # These will contain the initialized devices
    climates = hass.data[DOMAIN][CLIMATE_DOMAIN] = []

    session = async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True))
    aqualink = AqualinkClient(username, password, session)
    try:
        await aqualink.login()
    except AqualinkLoginException as login_exception:
        _LOGGER.error("Exception raised while attempting to login: %s", login_exception)
        return False

    systems = await aqualink.get_systems()
    systems = list(systems.values())
    if not systems:
        _LOGGER.error("No systems detected or supported")
        return False

    # Only supporting the first system for now.
    devices = await systems[0].get_devices()

    for dev in devices.values():
        if isinstance(dev, AqualinkThermostat):
            climates += [dev]

    forward_setup = hass.config_entries.async_forward_entry_setup
    if climates:
        _LOGGER.debug("Got %s climates: %s", len(climates), climates)
        hass.async_create_task(forward_setup(entry, CLIMATE_DOMAIN))

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload

    tasks = []

    if hass.data[DOMAIN][CLIMATE_DOMAIN]:
        tasks += [forward_unload(entry, CLIMATE_DOMAIN)]

    hass.data[DOMAIN].clear()

    return all(await asyncio.gather(*tasks))

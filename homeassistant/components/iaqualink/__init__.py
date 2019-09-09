"""Component to embed Aqualink devices."""
import asyncio
from functools import wraps
import logging

from aiohttp import CookieJar
import voluptuous as vol

from iaqualink import (
    AqualinkClient,
    AqualinkLight,
    AqualinkLoginException,
    AqualinkThermostat,
)

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DOMAIN, UPDATE_INTERVAL


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
    lights = hass.data[DOMAIN][LIGHT_DOMAIN] = []

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
        elif isinstance(dev, AqualinkLight):
            lights += [dev]

    forward_setup = hass.config_entries.async_forward_entry_setup
    if climates:
        _LOGGER.debug("Got %s climates: %s", len(climates), climates)
        hass.async_create_task(forward_setup(entry, CLIMATE_DOMAIN))
    if lights:
        _LOGGER.debug("Got %s lights: %s", len(lights), lights)
        hass.async_create_task(forward_setup(entry, LIGHT_DOMAIN))

    async def _async_systems_update(now):
        """Refresh internal state for all systems."""
        await systems[0].update()
        async_dispatcher_send(hass, DOMAIN)

    async_track_time_interval(hass, _async_systems_update, UPDATE_INTERVAL)

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload

    tasks = []

    if hass.data[DOMAIN][CLIMATE_DOMAIN]:
        tasks += [forward_unload(entry, CLIMATE_DOMAIN)]
    if hass.data[DOMAIN][LIGHT_DOMAIN]:
        tasks += [forward_unload(entry, LIGHT_DOMAIN)]

    hass.data[DOMAIN].clear()

    return all(await asyncio.gather(*tasks))


def refresh_system(func):
    """Force update all entities after state change."""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        """Call decorated function and send update signal to all entities."""
        await func(self, *args, **kwargs)
        async_dispatcher_send(self.hass, DOMAIN)

    return wrapper


class AqualinkEntity(Entity):
    """Abstract class for all Aqualink platforms."""

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._update_callback)

    @callback
    def _update_callback(self) -> None:
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def should_poll(self) -> bool:
        """Return False as entities shouldn't be polled.

        Entities are checked periodically as the integration runs periodic
        updates on a timer.
        """
        return False

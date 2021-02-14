"""Support for the Hive devices and services."""
import asyncio
from functools import wraps
import logging

from aiohttp.web_exceptions import HTTPException
from pyhiveapi import Hive
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_ONOFF,
    ATTR_TIME_PERIOD,
    DOMAIN,
    PLATFORMS,
    SERVICE_BOOST_HEATING,
    SERVICE_BOOST_HOT_WATER,
    SERVICES,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=2): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

BOOST_HEATING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_TIME_PERIOD): vol.All(
            cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds() // 60
        ),
        vol.Optional(ATTR_TEMPERATURE, default="25.0"): vol.Coerce(float),
    }
)

BOOST_HOT_WATER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_TIME_PERIOD, default="00:30:00"): vol.All(
            cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds() // 60
        ),
        vol.Required(ATTR_ONOFF): cv.string,
    }
)


async def async_setup(hass, config):
    """Set up the Hive Integration."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_USERNAME: conf[CONF_USERNAME],
                    CONF_PASSWORD: conf[CONF_PASSWORD],
                    CONF_SCAN_INTERVAL: conf.get(CONF_SCAN_INTERVAL, 120),
                },
            )
        )
    return True


async def async_setup_entry(hass, entry):
    """Set up Hive from a config entry."""
    # Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    websession = aiohttp_client.async_get_clientsession(hass)
    hive = Hive(websession)
    hive_config = dict(entry.data)
    hive_options = dict(entry.options)

    async def heating_boost(service):
        """Handle the service call."""

        entity_lookup = hass.data[DOMAIN]["entity_lookup"]
        device = entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not device:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return

        minutes = service.data[ATTR_TIME_PERIOD]
        temperature = service.data[ATTR_TEMPERATURE]

        await hive.heating.turn_boost_on(device, minutes, temperature)

    async def hot_water_boost(service):
        """Handle the service call."""
        entity_lookup = hass.data[DOMAIN]["entity_lookup"]
        device = entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not device:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return

        minutes = service.data[ATTR_TIME_PERIOD]
        mode = service.data[ATTR_ONOFF]

        if mode == "on":
            await hive.hotwater.turn_boost_on(device, minutes)
        elif mode == "off":
            await hive.hotwater.turn_boost_off(device)

        # Update config entry options

    hive_options = hive_options if len(hive_options) > 0 else hive_config["options"]
    hive_config["options"].update(hive_options)
    hive_config["add_sensors"] = (
        True if "hive" in hass.data["custom_components"] else False
    )
    hass.config_entries.async_update_entry(entry, options=hive_options)
    hass.data[DOMAIN][entry.entry_id] = hive
    hass.data[DOMAIN]["entity_lookup"] = {}

    try:
        hive.devices = await hive.session.startSession(hive_config)
    except HTTPException as error:
        _LOGGER.error("Could not connect to the internet: %s", error)
        raise ConfigEntryNotReady() from error

    if hive.devices == "INVALID_REAUTH":
        return hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
            )
        )

    for component in PLATFORMS:
        devicelist = hive.devices.get(component)
        if devicelist:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )
            if component == "climate":
                hass.services.async_register(
                    DOMAIN,
                    SERVICE_BOOST_HEATING,
                    heating_boost,
                    schema=BOOST_HEATING_SCHEMA,
                )
            if component == "water_heater":
                hass.services.async_register(
                    DOMAIN,
                    SERVICE_BOOST_HOT_WATER,
                    hot_water_boost,
                    schema=BOOST_HOT_WATER_SCHEMA,
                )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def refresh_system(func):
    """Force update all entities after state change."""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        await func(self, *args, **kwargs)
        async_dispatcher_send(self.hass, DOMAIN)

    return wrapper


class HiveEntity(Entity):
    """Initiate Hive Base Class."""

    def __init__(self, hive, hive_device):
        """Initialize the instance."""
        self.hive = hive
        self.device = hive_device
        self.attributes = {}
        self._unique_id = f'{self.device["hiveID"]}-{self.device["hiveType"]}'

    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )
        if self.device["hiveType"] in SERVICES:
            entity_lookup = self.hass.data[DOMAIN]["entity_lookup"]
            entity_lookup[self.entity_id] = self.device

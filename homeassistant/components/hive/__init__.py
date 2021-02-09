"""Support for the Hive devices and services."""
from functools import wraps
import logging

from pyhiveapi import Hive
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_AVAILABLE = "available"
ATTR_MODE = "mode"
DOMAIN = "hive"
DATA_HIVE = "data_hive"
SERVICES = ["Heating", "HotWater", "TRV"]
SERVICE_BOOST_HOT_WATER = "boost_hot_water"
SERVICE_BOOST_HEATING = "boost_heating"
ATTR_TIME_PERIOD = "time_period"
ATTR_MODE = "on_off"
DEVICETYPES = {
    "binary_sensor": "device_list_binary_sensor",
    "climate": "device_list_climate",
    "water_heater": "device_list_water_heater",
    "light": "device_list_light",
    "switch": "device_list_plug",
    "sensor": "device_list_sensor",
}

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
        vol.Required(ATTR_MODE): cv.string,
    }
)


async def async_setup(hass, config):
    """Set up the Hive Component."""

    async def heating_boost(service):
        """Handle the service call."""

        entity_lookup = hass.data[DOMAIN]["entity_lookup"]
        hive_id = entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not hive_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return

        minutes = service.data[ATTR_TIME_PERIOD]
        temperature = service.data[ATTR_TEMPERATURE]

        hive.heating.turn_boost_on(hive_id, minutes, temperature)

    async def hot_water_boost(service):
        """Handle the service call."""
        entity_lookup = hass.data[DOMAIN]["entity_lookup"]
        hive_id = entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not hive_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return
        minutes = service.data[ATTR_TIME_PERIOD]
        mode = service.data[ATTR_MODE]

        if mode == "on":
            hive.hotwater.turn_boost_on(hive_id, minutes)
        elif mode == "off":
            hive.hotwater.turn_boost_off(hive_id)

    hive = Hive()

    config = {}
    config["username"] = config[DOMAIN][CONF_USERNAME]
    config["password"] = config[DOMAIN][CONF_PASSWORD]
    config["update_interval"] = config[DOMAIN][CONF_SCAN_INTERVAL]

    devices = await hive.session.startSession(config)

    if devices is None:
        _LOGGER.error("Hive API initialization failed")
        return False

    hass.data[DOMAIN][DATA_HIVE] = hive
    hass.data[DOMAIN]["entity_lookup"] = {}

    for ha_type in DEVICETYPES:
        devicelist = devices.get(DEVICETYPES[ha_type])
        if devicelist:
            hass.async_create_task(
                async_load_platform(hass, ha_type, DOMAIN, devicelist, config)
            )
            if ha_type == "climate":
                hass.services.async_register(
                    DOMAIN,
                    SERVICE_BOOST_HEATING,
                    heating_boost,
                    schema=BOOST_HEATING_SCHEMA,
                )
            if ha_type == "water_heater":
                hass.services.async_register(
                    DOMAIN,
                    SERVICE_BOOST_HOT_WATER,
                    hot_water_boost,
                    schema=BOOST_HOT_WATER_SCHEMA,
                )

    return True


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
            entity_lookup[self.entity_id] = self.device["hiveID"]

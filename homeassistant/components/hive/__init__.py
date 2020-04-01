"""Support for the Hive devices and services."""
from functools import wraps
import logging

from pyhiveapi import Pyhiveapi
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

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


class HiveSession:
    """Initiate Hive Session Class."""

    entity_lookup = {}
    core = None
    heating = None
    hotwater = None
    light = None
    sensor = None
    switch = None
    weather = None
    attributes = None
    trv = None


def setup(hass, config):
    """Set up the Hive Component."""

    def heating_boost(service):
        """Handle the service call."""
        node_id = HiveSession.entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not node_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return

        minutes = service.data[ATTR_TIME_PERIOD]
        temperature = service.data[ATTR_TEMPERATURE]

        session.heating.turn_boost_on(node_id, minutes, temperature)

    def hot_water_boost(service):
        """Handle the service call."""
        node_id = HiveSession.entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not node_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return
        minutes = service.data[ATTR_TIME_PERIOD]
        mode = service.data[ATTR_MODE]

        if mode == "on":
            session.hotwater.turn_boost_on(node_id, minutes)
        elif mode == "off":
            session.hotwater.turn_boost_off(node_id)

    session = HiveSession()
    session.core = Pyhiveapi()

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    update_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    devices = session.core.initialise_api(username, password, update_interval)

    if devices is None:
        _LOGGER.error("Hive API initialization failed")
        return False

    session.sensor = Pyhiveapi.Sensor()
    session.heating = Pyhiveapi.Heating()
    session.hotwater = Pyhiveapi.Hotwater()
    session.light = Pyhiveapi.Light()
    session.switch = Pyhiveapi.Switch()
    session.weather = Pyhiveapi.Weather()
    session.attributes = Pyhiveapi.Attributes()
    hass.data[DATA_HIVE] = session

    for ha_type in DEVICETYPES:
        devicelist = devices.get(DEVICETYPES[ha_type])
        if devicelist:
            load_platform(hass, ha_type, DOMAIN, devicelist, config)
            if ha_type == "climate":
                hass.services.register(
                    DOMAIN,
                    SERVICE_BOOST_HEATING,
                    heating_boost,
                    schema=BOOST_HEATING_SCHEMA,
                )
            if ha_type == "water_heater":
                hass.services.register(
                    DOMAIN,
                    SERVICE_BOOST_HOT_WATER,
                    hot_water_boost,
                    schema=BOOST_HOT_WATER_SCHEMA,
                )

    return True


def refresh_system(func):
    """Force update all entities after state change."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        func(self, *args, **kwargs)
        dispatcher_send(self.hass, DOMAIN)

    return wrapper


class HiveEntity(Entity):
    """Initiate Hive Base Class."""

    def __init__(self, session, hive_device):
        """Initialize the instance."""
        self.node_id = hive_device["Hive_NodeID"]
        self.node_name = hive_device["Hive_NodeName"]
        self.device_type = hive_device["HA_DeviceType"]
        self.node_device_type = hive_device["Hive_DeviceType"]
        self.session = session
        self.attributes = {}
        self._unique_id = f"{self.node_id}-{self.device_type}"
        self._unsub_disp = None

    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        self._unsub_disp = async_dispatcher_connect(
            self.hass, DOMAIN, self.async_write_ha_state
        )
        if self.device_type in SERVICES:
            self.session.entity_lookup[self.entity_id] = self.node_id

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self._unsub_disp()
        self._unsub_disp = None

"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hive/
"""
import logging
import voluptuous as vol

from homeassistant.const import (CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['pyhiveapi==0.2.5']

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'hive'
DATA_HIVE = 'data_hive'
DEVICETYPES = {
    'binary_sensor': 'device_list_binary_sensor',
    'climate': 'device_list_climate',
    'light': 'device_list_light',
    'switch': 'device_list_plug',
    'sensor': 'device_list_sensor',
    }

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=2): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


class HiveSession:
    """Initiate Hive Session Class."""

    entities = []
    core = None
    heating = None
    hotwater = None
    light = None
    sensor = None
    switch = None


def setup(hass, config):
    """Set up the Hive Component."""
    from pyhiveapi import Pyhiveapi

    session = HiveSession()
    session.core = Pyhiveapi()

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    update_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    devicelist = session.core.initialise_api(username,
                                             password,
                                             update_interval)

    if devicelist is None:
        _LOGGER.error("Hive API initialization failed")
        return False

    session.sensor = Pyhiveapi.Sensor()
    session.heating = Pyhiveapi.Heating()
    session.hotwater = Pyhiveapi.Hotwater()
    session.light = Pyhiveapi.Light()
    session.switch = Pyhiveapi.Switch()
    hass.data[DATA_HIVE] = session

    for ha_type, hive_type in DEVICETYPES.items():
        for key, devices in devicelist.items():
            if key == hive_type:
                for hivedevice in devices:
                    load_platform(hass, ha_type, DOMAIN, hivedevice, config)
    return True

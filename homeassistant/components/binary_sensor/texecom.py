"""
Support for texecom zone states- represented as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.texecom/
"""

import asyncio
import logging
import datetime

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.texecom import (
    DATA_EVL, ZONE_SCHEMA, CONF_ZONENUMBER, CONF_ZONENAME, CONF_PANELUUID,CONF_ZONETYPE, TexecomBinarySensor)
from homeassistant.const import ATTR_LAST_TRIP_TIME
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['texecom']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Texecom binary sensor devices."""
    configured_zones = discovery_info['zones']

    devices = []
    for zone_num in configured_zones:
        device_config_data = ZONE_SCHEMA(configured_zones[zone_num])
        device = TexecomBinarySensor(
            hass,
            device_config_data[CONF_ZONENUMBER],
            device_config_data[CONF_ZONENAME],
            device_config_data[CONF_ZONETYPE],
            False
          )
        devices.append(device)

    async_add_devices(devices)



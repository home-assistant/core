import asyncio
import logging

from homeassistant.components.binary_sensor import (BinarySensorDevice)
from homeassistant.components.deconz import DATA_DECONZ

DEPENDENCIES = ['deconz']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """
    """
    print('Binary sensor', discovery_info)
    if DATA_DECONZ in hass.data:
        sensors = hass.data[DATA_DECONZ].sensors

    for sensor_id, sensor in sensors.items():
        if sensor.type == 'ZHAPresence':
            print(sensor.__dict__)


    #async_add_devices([entity])


# class DeconzBinarySensor(BinarySensorDevice):
#     """Representation of an device."""

#     def __init__(self, hass):
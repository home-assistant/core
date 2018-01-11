"""
Battery Level Sensor for Nissan Leaf
"""

import logging
from datetime import timedelta

from homeassistant.components.sensor import ENTITY_ID_FORMAT
import custom_components.leaf as LeafCore
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']

def setup_platform(hass, config, add_devices, discovery_info=None):
    controller = hass.data[LeafCore.DATA_LEAF].leaf
    devices = []

    devices.append(LeafSensor(controller, hass.data[LeafCore.DATA_LEAF]))

    add_devices(devices, True)

class LeafSensor(Entity):
    def __init__(self, controller, data):
        self.controller = controller
        self.data = data

    @property
    def name(self):
        return "Leaf Charge %"
    
    @property
    def state(self):
        return self.data[LeafCore.DATA_BATTERY]

    @property
    def unit_of_measurement(self):
        return '%'

    def update(self):
        self.data.update()
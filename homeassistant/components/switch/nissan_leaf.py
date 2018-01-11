"""
Charge and Climate Switch for Nissan Leaf
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

    devices.append(LeafChargeSwitch(controller, hass.data[LeafCore.DATA_LEAF]))
    devices.append(LeafClimateSwitch(controller, hass.data[LeafCore.DATA_LEAF]))

    add_devices(devices, True)

class LeafClimateSwitch(Entity):
    def __init__(self, controller, data):
        self.controller = controller
        self.data = data

    @property
    def name(self):
        return "Leaf Climate Control"
    
    @property
    def is_on(self):
        return self.data[LeafCore.DATA_CLIMATE]

    def turn_on(self):
        if self.controller.set_climate(True):
            self.data[LeafCore.DATA_CLIMATE] = True

    def turn_off(self):
        if self.controller.set_climate(False):
            self.data[LeafCore.DATA_CLIMATE] = False
    
    def update(self):
        self.data.update()


class LeafChargeSwitch(Entity):
    def __init__(self, controller, data):
        self.controller = controller
        self.data = data

    @property
    def name(self):
        return "Leaf Charging Status"
    
    @property
    def is_on(self):
        return self.data[LeafCore.DATA_CHARGING]

    def turn_on(self):
        if self.controller.start_charging()
            self.data[LeafCore.DATA_CHARGING] = True

    def turn_off(self):
        _LOGGER.debug("Cannot turn off Leaf charging - Nissan does not support that remotely.")
    
    def update(self):
        self.data.update()

"""
Plugged In Status Support for the Nissan Leaf

Documentation pending.
Please refer to the main platform component for configuration details
"""

import logging

from .. import nissan_leaf as LeafCore

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    devices = []

    _LOGGER.debug("Adding sensors")

    for key, value in hass.data[LeafCore.DATA_LEAF].items():
        devices.append(LeafPluggedInSensor(value))

    add_devices(devices, True)

    return True


class LeafPluggedInSensor(LeafCore.LeafEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Plug Status"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafPluggedInSensor component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def state(self):
        return self.car.data[LeafCore.DATA_PLUGGED_IN]

    @property
    def icon(self):
        if self.car.data[LeafCore.DATA_PLUGGED_IN]:
            return 'mdi:power-plug'
        else:
            return 'mdi:power-plug-off'

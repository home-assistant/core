"""
Plugged In Status Support for the Nissan Leaf

Documentation pending.
Please refer to the main platform component for configuration details
"""

import logging

from .. import nissan_leaf as leaf_core

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']


def setup_platform(hass, config, add_devices, discovery_info=None):
    if discovery_info is None:
        return

    _LOGGER.debug("Adding sensors")

    devices = []
    for value in hass.data[leaf_core.DATA_LEAF].values():
        devices.append(LeafPluggedInSensor(value))

    add_devices(devices, True)


class LeafPluggedInSensor(leaf_core.LeafEntity):
    @property
    def name(self):
        return self.car.leaf.nickname + " Plug Status"

    def log_registration(self):
        _LOGGER.debug(
            "Registered LeafPluggedInSensor component with HASS for VIN %s",
            self.car.leaf.vin)

    @property
    def state(self):
        return self.car.data[leaf_core.DATA_PLUGGED_IN]

    @property
    def icon(self):
        if self.car.data[leaf_core.DATA_PLUGGED_IN]:
            return 'mdi:power-plug'
        else:
            return 'mdi:power-plug-off'

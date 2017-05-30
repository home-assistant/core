"""
Support for MySensors binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mysensors/
"""
import logging

from homeassistant.components import mysensors
from homeassistant.components.binary_sensor import (DEVICE_CLASSES,
                                                    BinarySensorDevice)
from homeassistant.const import STATE_ON

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MySensors platform for sensors."""
    # Only act if loaded via mysensors by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if not gateways:
        return

    for gateway in gateways:
        # Define the S_TYPES and V_TYPES that the platform should handle as
        # states. Map them in a dict of lists.
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_DOOR: [set_req.V_TRIPPED],
            pres.S_MOTION: [set_req.V_TRIPPED],
            pres.S_SMOKE: [set_req.V_TRIPPED],
        }
        if float(gateway.protocol_version) >= 1.5:
            map_sv_types.update({
                pres.S_SPRINKLER: [set_req.V_TRIPPED],
                pres.S_WATER_LEAK: [set_req.V_TRIPPED],
                pres.S_SOUND: [set_req.V_TRIPPED],
                pres.S_VIBRATION: [set_req.V_TRIPPED],
                pres.S_MOISTURE: [set_req.V_TRIPPED],
            })

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, MySensorsBinarySensor, add_devices))


class MySensorsBinarySensor(
        mysensors.MySensorsDeviceEntity, BinarySensorDevice):
    """Represent the value of a MySensors Binary Sensor child node."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        if self.value_type in self._values:
            return self._values[self.value_type] == STATE_ON
        return False

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        pres = self.gateway.const.Presentation
        class_map = {
            pres.S_DOOR: 'opening',
            pres.S_MOTION: 'motion',
            pres.S_SMOKE: 'smoke',
        }
        if float(self.gateway.protocol_version) >= 1.5:
            class_map.update({
                pres.S_SPRINKLER: 'sprinkler',
                pres.S_WATER_LEAK: 'leak',
                pres.S_SOUND: 'sound',
                pres.S_VIBRATION: 'vibration',
                pres.S_MOISTURE: 'moisture',
            })
        if class_map.get(self.child_type) in DEVICE_CLASSES:
            return class_map.get(self.child_type)

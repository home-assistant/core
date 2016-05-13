"""
Support for MySensors switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mysensors/
"""
import logging

from homeassistant.components import mysensors
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import STATE_OFF, STATE_ON

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for switches."""
    # Only act if loaded via mysensors by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    for gateway in mysensors.GATEWAYS.values():
        # Define the S_TYPES and V_TYPES that the platform should handle as
        # states. Map them in a dict of lists.
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_DOOR: [set_req.V_ARMED],
            pres.S_MOTION: [set_req.V_ARMED],
            pres.S_SMOKE: [set_req.V_ARMED],
            pres.S_LIGHT: [set_req.V_LIGHT],
            pres.S_LOCK: [set_req.V_LOCK_STATUS],
        }
        if float(gateway.version) >= 1.5:
            map_sv_types.update({
                pres.S_BINARY: [set_req.V_STATUS, set_req.V_LIGHT],
                pres.S_SPRINKLER: [set_req.V_STATUS],
                pres.S_WATER_LEAK: [set_req.V_ARMED],
                pres.S_SOUND: [set_req.V_ARMED],
                pres.S_VIBRATION: [set_req.V_ARMED],
                pres.S_MOISTURE: [set_req.V_ARMED],
            })
            map_sv_types[pres.S_LIGHT].append(set_req.V_STATUS)

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, MySensorsSwitch))


class MySensorsSwitch(mysensors.MySensorsDeviceEntity, SwitchDevice):
    """Representation of the value of a MySensors Switch child node."""

    @property
    def is_on(self):
        """Return True if switch is on."""
        if self.value_type in self._values:
            return self._values[self.value_type] == STATE_ON
        return False

    def turn_on(self):
        """Turn the switch on."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 1)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_ON
            self.update_ha_state()

    def turn_off(self):
        """Turn the switch off."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 0)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_OFF
            self.update_ha_state()

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return self.gateway.optimistic

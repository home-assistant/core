"""
Zwave platform that handles simple binary switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.components.zwave import (
    ATTR_NODE_ID, ATTR_VALUE_ID, COMMAND_CLASS_SWITCH_BINARY, GENRE_USER,
    NETWORK, TYPE_BOOL, ZWaveDeviceEntity)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Z-Wave switches."""
    if discovery_info is None or NETWORK is None:
        return

    node = NETWORK.nodes[discovery_info[ATTR_NODE_ID]]
    value = node.values[discovery_info[ATTR_VALUE_ID]]

    if value.command_class != COMMAND_CLASS_SWITCH_BINARY:
        return
    if value.type != TYPE_BOOL:
        return
    if value.genre != GENRE_USER:
        return

    value.set_change_verified(False)
    add_devices([ZwaveSwitch(value)])


class ZwaveSwitch(ZWaveDeviceEntity, SwitchDevice):
    """Representation of a Z-Wave switch."""

    def __init__(self, value):
        """Initialize the Z-Wave switch device."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        ZWaveDeviceEntity.__init__(self, value, DOMAIN)

        self._state = value.data
        dispatcher.connect(
            self._value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def _value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id:
            self._state = value.data
            self.update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._value.node.set_switch(self._value.value_id, True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._value.node.set_switch(self._value.value_id, False)

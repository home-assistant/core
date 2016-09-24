"""
Z-Wave platform that handles simple binary switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.components import zwave


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Z-Wave platform."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]

    if not node.has_command_class(zwave.const.COMMAND_CLASS_SWITCH_BINARY):
        return
    if value.type != zwave.const.TYPE_BOOL or value.genre != \
       zwave.const.GENRE_USER:
        return

    value.set_change_verified(False)
    add_devices([ZwaveSwitch(value)])


class ZwaveSwitch(zwave.ZWaveDeviceEntity, SwitchDevice):
    """Representation of a Z-Wave switch."""

    def __init__(self, value):
        """Initialize the Z-Wave switch device."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)

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

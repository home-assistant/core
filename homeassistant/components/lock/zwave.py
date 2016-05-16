"""
Zwave platform that handles simple door locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.lock import DOMAIN, LockDevice
from homeassistant.components import zwave


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Z-Wave switches."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.ATTR_VALUE_ID]]

    if value.command_class != zwave.COMMAND_CLASS_DOOR_LOCK:
        return
    if value.type != zwave.TYPE_BOOL:
        return
    if value.genre != zwave.GENRE_USER:
        return

    value.set_change_verified(False)
    add_devices([ZwaveLock(value)])


class ZwaveLock(zwave.ZWaveDeviceEntity, LockDevice):
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
    def is_locked(self):
        """Return true if device is locked."""
        return self._state

    def lock(self, **kwargs):
        """Lock the device."""
        self._value.data = True

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._value.data = False

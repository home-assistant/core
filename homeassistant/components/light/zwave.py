"""
homeassistant.components.light.zwave
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
# pylint: disable=import-error
from openzwave.network import ZWaveNetwork
from pydispatch import dispatcher

import homeassistant.components.zwave as zwave

from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.light import (Light, ATTR_BRIGHTNESS)
from time import sleep


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and add zwave lights. """
    if discovery_info is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.ATTR_VALUE_ID]]

    if value.command_class != zwave.COMMAND_CLASS_SWITCH_MULTILEVEL:
        return
    if value.type != zwave.TYPE_BYTE:
        return
    if value.genre != zwave.GENRE_USER:
        return

    value.set_change_verified(False)
    add_devices([ZwaveDimmer(value)])


def brightness_state(value):
    """ Returns the brightness and state according to the current
    data of given value. """
    if value.data > 0:
        return (value.data / 99) * 255, STATE_ON
    else:
        return 255, STATE_OFF


class ZwaveDimmer(Light):
    """ Provides a zwave dimmer. """
    # pylint: disable=too-many-arguments
    def __init__(self, value):
        self._value = value
        self._node = value.node

        self._brightness, self._state = brightness_state(value)

        # Used for value change event handling
        self._refreshing = False
        self._expect = None

        dispatcher.connect(
            self._value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def _value_changed(self, value):
        """ Called when a value has changed on the network. """
        if self._value.value_id == value.value_id:
            # leoc: Since my multilevel switches dim slowly between
            # brightness levels / states, the value_change event does
            # not return the new end state, but rather the state the
            # the switch was at, before changing. Thus we have to wait
            # 2 seconds until the change is done...
            if self._refreshing:
                self._refreshing = False
                brightness, state = brightness_state(value)
                print("Refresh: ", brightness, ", ", state, ", ", self._expect)
                if self._expect is None or self._expect == state:
                    print("Is expected!")
                    self._brightness, self._state = brightness, state
                    self._expect = None
                    self.update_ha_state()
                else:
                    print("Not expected!")
            else:
                self._refreshing = True
                print("Value change: sleeping")
                sleep(2)
                value.refresh()

    @property
    def should_poll(self):
        """ No polling needed for a light. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        name = self._node.name or "{}".format(self._node.product_name)

        return "{}".format(name or self._value.label)

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return self._brightness

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turn the device on. """

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        # Zwave multilevel switches use a range of [0, 99] to control
        # brightness ...
        brightness = (self._brightness / 255) * 99

        print("Turn on", self._brightness, brightness)

        self._expect = STATE_ON
        if self._node.set_dimmer(self._value.value_id, brightness):
            self._state = STATE_ON
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        print("Turn off")

        self._expect = STATE_OFF
        if self._node.set_dimmer(self._value.value_id, 0):
            self._state = STATE_OFF
        self.update_ha_state()

"""
homeassistant.components.light.zwave
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Z-Wave lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.zwave/
"""
# pylint: disable=import-error
import homeassistant.components.zwave as zwave

from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.light import (Light, ATTR_BRIGHTNESS,
                                            ATTR_TRANSITION)
from threading import Timer


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and add Z-Wave lights. """
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
    """
    Returns the brightness and state according to the current data of given
    value.
    """
    if value.data > 0:
        return (value.data / 99) * 255, STATE_ON
    else:
        return 255, STATE_OFF


class ZwaveDimmer(Light):
    """ Provides a Z-Wave dimmer. """
    # pylint: disable=too-many-arguments
    def __init__(self, value):
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        self._value = value
        self._node = value.node

        self._brightness, self._state = brightness_state(value)

        # Used to track actual brightness of light when fading on/off using a
        # transition
        if self._state == STATE_ON:
            self._current_brightness = int(self._brightness / 255 * 99)
        else:
            self._current_brightness = 0

        # Used for value change event handling
        self._refreshing = False
        self._timer = None

        # Used for emulating a slow transition
        self._transition_timer = None

        dispatcher.connect(
            self._value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def _value_changed(self, value):
        """ Called when a value has changed on the network. """
        if self._value.value_id != value.value_id:
            return

        if self._refreshing:
            self._refreshing = False
            self._brightness, self._state = brightness_state(value)
        else:
            def _refresh_value():
                """Used timer callback for delayed value refresh."""
                self._refreshing = True
                self._value.refresh()

            if self._timer is not None and self._timer.isAlive():
                self._timer.cancel()

            self._timer = Timer(2, _refresh_value)
            self._timer.start()

        self.update_ha_state()

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

        if self._transition_timer is not None:
            self._transition_timer.cancel()

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        # Zwave multilevel switches use a range of [0, 99] to control
        # brightness.
        brightness = (self._brightness / 255) * 99

        # If 0, then just send command to turn on light immediately. Some dimmer
        # switches will still have a fade-on period that's built into the
        # hardware.
        transition = kwargs.get(ATTR_TRANSITION, 0)
        # TODO: Is there a minimum transition interval below which this doesn't
        # work? If so, we may need to add a check for that and then use larger
        # brightness steps.

        # Update interval specifies the time (in seconds) between each increment
        # of brightness by a value of 1 (0 to 99).
        update_interval = transition/brightness

        # If transition is immediate, jump to the final level.
        brightness_step = 1 if transition != 0 else brightness

        self._transition_update(brightness_step, brightness, update_interval)

    def _transition_update(self, brightness_step, target_brightness,
                           update_interval):

        brightness = self._current_brightness + brightness_step
        if self._node.set_dimmer(self._value.value_id, brightness):
            if brightness != 0:
                self._state = STATE_ON
            else:
                self._state = STATE_OFF
            self._current_brightness = brightness

        if brightness != target_brightness:
            args = (brightness_step, target_brightness, update_interval)
            self._transition_timer = \
                Timer(update_interval, self._transition_update, args).start()

    def turn_off(self, **kwargs):
        """ Turn the device off. """

        if self._transition_timer is not None:
            self._transition_timer.cancel()

        transition = kwargs.get(ATTR_TRANSITION, 0)
        update_interval = transition/self._current_brightness
        brightness_step = -1 if transition != 0 else -self._current_brightness
        self._transition_update(brightness_step, 0, update_interval)

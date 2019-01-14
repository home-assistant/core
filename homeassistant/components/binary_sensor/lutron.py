"""
Binary sensor for Lutron RadioRA2 keypad buttons.

There are two classes of button: raise/lower buttons that have discrete
press/release events (e.g., dimmer buttons) and single-action buttons
that only have press events.

A sensor for a raise/lower button is "on" when the button is pressed and
"off" when it's released.

A sensor for a single-action button goes from "off" to "on" and then
immediately back to "off" when the button is clicked, that is, it
appears to be pressed and then released instantaneously.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lutron/
"""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.lutron import LUTRON_DEVICES

DEPENDENCIES = ['lutron']
REQUIREMENTS = ['pylutron==0.2.0']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lutron RadioRA2 binary sensor platform."""
    if LUTRON_DEVICES not in hass.data:
        return
    if 'binary_sensor' not in hass.data[LUTRON_DEVICES]:
        return

    for (name, button) in hass.data[LUTRON_DEVICES]['binary_sensor']:
        sensor = LutronButtonSensor(name, button, hass)
        add_devices([sensor])
        sensor.listen()


class LutronButtonSensor(BinarySensorDevice):
    """Representation of a Lutron RadioRA2 button."""

    def __init__(self, name, button, hass):
        """Initialize the demo sensor."""
        self._name = name
        self._state = False   # Default to non-pressed
        self._button = button
        self._hass = hass
        self._has_release_event = 'RaiseLower' in button.button_type

    def listen(self):
        """Start listening for events from the Lutron repeater."""
        self._button.subscribe(self.handle_event, None)

    def handle_event(self, button, context, event, params):
        """Handle a button press or release event."""
        from pylutron import Button

        if self._has_release_event:
            if event == Button.Event.PRESSED:
                self._state = True
            else:
                self._state = False
            self._hass.states.set(self.entity_id, self._state)
        else:
            # The controller doesn't expose separate press/release states
            # for single-action buttons, so publish two state changes in
            # rapid succession to let automations trigger on the state
            # transition.
            self._hass.states.set(self.entity_id, True)
            self._hass.states.set(self.entity_id, False)

    @property
    def should_poll(self):
        """No polling needed because we get notifications from pylutron."""
        return False

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

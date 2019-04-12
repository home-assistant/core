"""Component for interacting with a Lutron RadioRA 2 system."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ID, CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

DOMAIN = 'lutron'

_LOGGER = logging.getLogger(__name__)

LUTRON_BUTTONS = 'lutron_buttons'
LUTRON_CONTROLLER = 'lutron_controller'
LUTRON_DEVICES = 'lutron_devices'

# Attribute on events that indicates what action was taken with the button.
ATTR_ACTION = 'action'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, base_config):
    """Set up the Lutron component."""
    from pylutron import Lutron

    hass.data[LUTRON_BUTTONS] = []
    hass.data[LUTRON_CONTROLLER] = None
    hass.data[LUTRON_DEVICES] = {'light': [],
                                 'cover': [],
                                 'switch': [],
                                 'scene': []}

    config = base_config.get(DOMAIN)
    hass.data[LUTRON_CONTROLLER] = Lutron(
        config[CONF_HOST], config[CONF_USERNAME], config[CONF_PASSWORD])

    hass.data[LUTRON_CONTROLLER].load_xml_db()
    hass.data[LUTRON_CONTROLLER].connect()
    _LOGGER.info("Connected to main repeater at %s", config[CONF_HOST])

    # Sort our devices into types
    for area in hass.data[LUTRON_CONTROLLER].areas:
        for output in area.outputs:
            if output.type == 'SYSTEM_SHADE':
                hass.data[LUTRON_DEVICES]['cover'].append((area.name, output))
            elif output.is_dimmable:
                hass.data[LUTRON_DEVICES]['light'].append((area.name, output))
            else:
                hass.data[LUTRON_DEVICES]['switch'].append((area.name, output))
        for keypad in area.keypads:
            for button in keypad.buttons:
                # This is the best way to determine if a button does anything
                # useful until pylutron is updated to provide information on
                # which buttons actually control scenes.
                for led in keypad.leds:
                    if (led.number == button.number and
                            button.name != 'Unknown Button' and
                            button.button_type in ('SingleAction', 'Toggle')):
                        hass.data[LUTRON_DEVICES]['scene'].append(
                            (area.name, keypad.name, button, led))

                hass.data[LUTRON_BUTTONS].append(
                    LutronButton(hass, keypad, button))

    for component in ('light', 'cover', 'switch', 'scene'):
        discovery.load_platform(hass, component, DOMAIN, None, base_config)
    return True


class LutronDevice(Entity):
    """Representation of a Lutron device entity."""

    def __init__(self, area_name, lutron_device, controller):
        """Initialize the device."""
        self._lutron_device = lutron_device
        self._controller = controller
        self._area_name = area_name

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.async_add_executor_job(
            self._lutron_device.subscribe,
            self._update_callback,
            None
        )

    def _update_callback(self, _device, _context, _event, _params):
        """Run when invoked by pylutron when the device state changes."""
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return "{} {}".format(self._area_name, self._lutron_device.name)

    @property
    def should_poll(self):
        """No polling needed."""
        return False


class LutronButton:
    """Representation of a button on a Lutron keypad.

    This is responsible for firing events as keypad buttons are pressed
    (and possibly released, depending on the button type). It is not
    represented as an entity; it simply fires events.
    """

    def __init__(self, hass, keypad, button):
        """Register callback for activity on the button."""
        name = '{}: {}'.format(keypad.name, button.name)
        self._hass = hass
        self._has_release_event = (button.button_type is not None and
                                   'RaiseLower' in button.button_type)
        self._id = slugify(name)
        self._event = 'lutron_event'

        button.subscribe(self.button_callback, None)

    def button_callback(self, button, context, event, params):
        """Fire an event about a button being pressed or released."""
        from pylutron import Button

        # Events per button type:
        #   RaiseLower -> pressed/released
        #   SingleAction -> single
        action = None
        if self._has_release_event:
            if event == Button.Event.PRESSED:
                action = 'pressed'
            else:
                action = 'released'
        elif event == Button.Event.PRESSED:
            action = 'single'

        if action:
            data = {ATTR_ID: self._id, ATTR_ACTION: action}
            self._hass.bus.fire(self._event, data)

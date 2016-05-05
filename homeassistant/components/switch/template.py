"""
Support for switches which integrates with other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.template/
"""
import logging

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, CONF_VALUE_TEMPLATE, STATE_OFF, STATE_ON)
from homeassistant.core import EVENT_STATE_CHANGED
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.service import call_from_config
from homeassistant.helpers import template
from homeassistant.util import slugify

CONF_SWITCHES = 'switches'

ON_ACTION = 'turn_on'
OFF_ACTION = 'turn_off'

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, 'true', 'false']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Template switch."""
    switches = []
    if config.get(CONF_SWITCHES) is None:
        _LOGGER.error("Missing configuration data for switch platform")
        return False

    for device, device_config in config[CONF_SWITCHES].items():

        if device != slugify(device):
            _LOGGER.error("Found invalid key for switch.template: %s. "
                          "Use %s instead", device, slugify(device))
            continue

        if not isinstance(device_config, dict):
            _LOGGER.error("Missing configuration data for switch %s", device)
            continue

        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        on_action = device_config.get(ON_ACTION)
        off_action = device_config.get(OFF_ACTION)
        if state_template is None:
            _LOGGER.error(
                "Missing %s for switch %s", CONF_VALUE_TEMPLATE, device)
            continue

        if on_action is None or off_action is None:
            _LOGGER.error(
                "Missing action for switch %s", device)
            continue

        switches.append(
            SwitchTemplate(
                hass,
                device,
                friendly_name,
                state_template,
                on_action,
                off_action)
            )
    if not switches:
        _LOGGER.error("No switches added")
        return False
    add_devices(switches)
    return True


class SwitchTemplate(SwitchDevice):
    """Representation of a Template switch."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, device_id, friendly_name, state_template,
                 on_action, off_action):
        """Initialize the Template switch."""
        self.hass = hass
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, device_id,
                                            hass=hass)
        self._name = friendly_name
        self._template = state_template
        self._on_action = on_action
        self._off_action = off_action
        self._state = False

        self.update()

        def template_switch_event_listener(event):
            """Called when the target device changes state."""
            self.update_ha_state(True)

        hass.bus.listen(EVENT_STATE_CHANGED,
                        template_switch_event_listener)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """If switch is available."""
        return self._state is not None

    def turn_on(self, **kwargs):
        """Fire the on action."""
        call_from_config(self.hass, self._on_action, True)

    def turn_off(self, **kwargs):
        """Fire the off action."""
        call_from_config(self.hass, self._off_action, True)

    def update(self):
        """Update the state from the template."""
        try:
            state = template.render(self.hass, self._template).lower()

            if state in _VALID_STATES:
                self._state = state in ('true', STATE_ON)
            else:
                _LOGGER.error(
                    'Received invalid switch is_on state: %s. Expected: %s',
                    state, ', '.join(_VALID_STATES))
                self._state = None

        except TemplateError as ex:
            _LOGGER.error(ex)
            self._state = None

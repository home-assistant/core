"""
Support for switches which integrates with other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.template/
"""
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, CONF_VALUE_TEMPLATE, STATE_OFF, STATE_ON)
from homeassistant.core import EVENT_STATE_CHANGED
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.service import call_from_config
from homeassistant.helpers import template
from homeassistant.util import slugify

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)

CONF_SWITCHES = 'switches'

STATE_ERROR = 'error'

ON_ACTION = 'turn_on'
OFF_ACTION = 'turn_off'


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
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, device_id,
                                            hass=hass)
        self.hass = hass
        self._name = friendly_name
        self._template = state_template
        self._on_action = on_action
        self._off_action = off_action
        self.update()
        self.hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)

    def _event_listener(self, event):
        """Called when the target device changes state."""
        if not hasattr(self, 'hass'):
            return
        self.update_ha_state(True)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def turn_on(self, **kwargs):
        """Fire the on action."""
        call_from_config(self.hass, self._on_action, True)

    def turn_off(self, **kwargs):
        """Fire the off action."""
        call_from_config(self.hass, self._off_action, True)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._value.lower() == 'true' or self._value == STATE_ON

    @property
    def is_off(self):
        """Return true if device is off."""
        return self._value.lower() == 'false' or self._value == STATE_OFF

    @property
    def available(self):
        """Return true if entity is available."""
        return self.is_on or self.is_off

    def update(self):
        """Update the state from the template."""
        try:
            self._value = template.render(self.hass, self._template)
            if not self.available:
                _LOGGER.error(
                    "`%s` is not a switch state, setting %s to unavailable",
                    self._value, self.entity_id)

        except TemplateError as ex:
            self._value = STATE_ERROR
            _LOGGER.error(ex)

"""
Component to interface with an alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel/
"""
import logging
import os

import voluptuous as vol

from homeassistant.const import (
    ATTR_CODE, ATTR_CODE_FORMAT, ATTR_ENTITY_ID, SERVICE_ALARM_TRIGGER,
    SERVICE_ALARM_DISARM, SERVICE_ALARM_ARM_HOME, SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_KEYPRESS, SERVICE_ALARM_OUTPUT_CONTROL)
from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'alarm_control_panel'
SCAN_INTERVAL = 30
ATTR_CHANGED_BY = 'changed_by'
ATTR_KEYPRESS = 'keypress'
ATTR_OUTPUT = 'output'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ALARM_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_CODE): cv.string
})

ALARM_KEYPRESS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_KEYPRESS): cv.string
})

ALARM_OUTPUT_CONTROL_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_OUTPUT):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
})

SERVICE_TO_METHOD = {
    SERVICE_ALARM_DISARM: {'method': 'alarm_disarm'},
    SERVICE_ALARM_ARM_HOME: {'method': 'alarm_arm_home'},
    SERVICE_ALARM_ARM_AWAY: {'method': 'alarm_arm_away'},
    SERVICE_ALARM_TRIGGER: {'method': 'alarm_trigger'},
    SERVICE_ALARM_KEYPRESS: {
        'method': 'alarm_keypress',
        'schema': ALARM_KEYPRESS_SCHEMA},
    SERVICE_ALARM_OUTPUT_CONTROL: {
        'method': 'alarm_output_control',
        'schema': ALARM_OUTPUT_CONTROL_SCHEMA}
}


def setup(hass, config):
    """Track states and offer events for sensors."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    component.setup(config)

    def alarm_service_handler(service):
        """Handle calls to the alarm control panel services."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = service.data.copy()
        params.pop(ATTR_ENTITY_ID, None)

        if method:
            for alarm_control_panel in component.extract_from_service(service):
                getattr(alarm_control_panel, method['method'])(**params)

                if alarm_control_panel.should_poll:
                    alarm_control_panel.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    for service_name in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service_name].get(
            'schema', ALARM_SERVICE_SCHEMA)
        hass.services.register(DOMAIN, service_name, alarm_service_handler,
                               descriptions.get(service_name), schema=schema)
    return True


def alarm_disarm(hass, code=None, entity_id=None):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_DISARM, data)


def alarm_arm_home(hass, code=None, entity_id=None):
    """Send the alarm the command for arm home."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_ARM_HOME, data)


def alarm_arm_away(hass, code=None, entity_id=None):
    """Send the alarm the command for arm away."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_ARM_AWAY, data)


def alarm_trigger(hass, code=None, entity_id=None):
    """Send the alarm the command for trigger."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_TRIGGER, data)


def alarm_keypress(hass, keypress, entity_id=None):
    """Send a custom key sequence to the alarm."""
    data = {}
    data[ATTR_KEYPRESS] = keypress
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_KEYPRESS, data)


def alarm_output_control(hass, output, entity_id=None):
    """Toggle an output on the alarm."""
    data = {}
    data[ATTR_OUTPUT] = output
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_OUTPUT_CONTROL, data)


# pylint: disable=no-self-use
class AlarmControlPanel(Entity):
    """An abstract class for alarm control devices."""

    @property
    def code_format(self):
        """Regex for code format or None if no code is required."""
        return None

    @property
    def changed_by(self):
        """Last change triggered by."""
        return None

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        raise NotImplementedError()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        raise NotImplementedError()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        raise NotImplementedError()

    def alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        raise NotImplementedError()

    def alarm_keypress(self, keypress=None):
        """Send custom key sequence to alarm."""
        pass

    def alarm_output_control(self, output=None):
        """Control an output on the alarm."""
        pass

    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by
        }
        return state_attr

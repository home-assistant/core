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
    SERVICE_ALARM_KEYPRESS, SERVICE_ALARM_OUTPUT_CONTROL )
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

SERVICE_TO_METHOD = {
    SERVICE_ALARM_DISARM: 'alarm_disarm',
    SERVICE_ALARM_ARM_HOME: 'alarm_arm_home',
    SERVICE_ALARM_ARM_AWAY: 'alarm_arm_away',
    SERVICE_ALARM_TRIGGER: 'alarm_trigger',
    SERVICE_ALARM_KEYPRESS: 'alarm_keypress',
    SERVICE_ALARM_OUTPUT_CONTROL: 'alarm_output_control'
}

ATTR_TO_PROPERTY = [
    ATTR_CODE,
    ATTR_CODE_FORMAT
]

ALARM_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_CODE): cv.string,
    vol.Optional(ATTR_KEYPRESS): cv.string,
    vol.Optional(ATTR_OUTPUT): cv.string
})


def setup(hass, config):
    """Track states and offer events for sensors."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    component.setup(config)

    def alarm_service_handler(service):
        """Map services to methods on Alarm."""
        target_alarms = component.extract_from_service(service)
        code = service.data.get(ATTR_CODE)

        for alarm in target_alarms:            
            if service.service == 'alarm_disarm':
            	alarm.alarm_disarm(code)
            elif service.service == 'alarm_arm_home':
            	alarm.alarm_arm_home(code)
            elif service.service == 'alarm_arm_away':
                alarm.alarm_arm_away(code)
            elif service.service == 'alarm_trigger':
                alarm.alarm_trigger(code)
            elif service.service == 'alarm_keypress':
                keypress = service.data.get(ATTR_KEYPRESS)
                alarm.alarm_keypress(keypress)
            elif service.service == 'alarm_output_control':
                output = service.data.get(ATTR_OUTPUT)
                alarm.alarm_output_control(output)
            
            if alarm.should_poll:
                alarm.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    for service in SERVICE_TO_METHOD:
        hass.services.register(DOMAIN, service, alarm_service_handler,
                               descriptions.get(service),
                               schema=ALARM_SERVICE_SCHEMA)
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
    if keypress:
        data[ATTR_KEYPRESS] = keypress
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_KEYPRESS, data)
    
def alarm_output_control(hass, output, entity_id=None):
    """Toggle an output on the alarm"""
    data = {}
    if output:
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
        raise NotImplementedError()

    def alarm_output_control(self, output=None):
        """Control an output on the alarm"""
        raise NotImplementedError()

    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by
        }
        return state_attr

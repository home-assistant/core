"""Component to interface with an alarm control panel."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_CODE, ATTR_CODE_FORMAT, ATTR_ENTITY_ID, SERVICE_ALARM_TRIGGER,
    SERVICE_ALARM_DISARM, SERVICE_ALARM_ARM_HOME, SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_NIGHT, SERVICE_ALARM_ARM_CUSTOM_BYPASS)
from homeassistant.helpers.config_validation import (  # noqa
    PLATFORM_SCHEMA, PLATFORM_SCHEMA_BASE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'alarm_control_panel'
SCAN_INTERVAL = timedelta(seconds=30)
ATTR_CHANGED_BY = 'changed_by'
FORMAT_TEXT = 'text'
FORMAT_NUMBER = 'number'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ALARM_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Optional(ATTR_CODE): cv.string,
})


async def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_ALARM_DISARM, ALARM_SERVICE_SCHEMA,
        'async_alarm_disarm'
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_HOME, ALARM_SERVICE_SCHEMA,
        'async_alarm_arm_home'
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_AWAY, ALARM_SERVICE_SCHEMA,
        'async_alarm_arm_away'
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_NIGHT, ALARM_SERVICE_SCHEMA,
        'async_alarm_arm_night'
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_CUSTOM_BYPASS, ALARM_SERVICE_SCHEMA,
        'async_alarm_arm_custom_bypass'
    )
    component.async_register_entity_service(
        SERVICE_ALARM_TRIGGER, ALARM_SERVICE_SCHEMA,
        'async_alarm_trigger'
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


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

    def async_alarm_disarm(self, code=None):
        """Send disarm command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_executor_job(self.alarm_disarm, code)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        raise NotImplementedError()

    def async_alarm_arm_home(self, code=None):
        """Send arm home command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_executor_job(self.alarm_arm_home, code)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        raise NotImplementedError()

    def async_alarm_arm_away(self, code=None):
        """Send arm away command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_executor_job(self.alarm_arm_away, code)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        raise NotImplementedError()

    def async_alarm_arm_night(self, code=None):
        """Send arm night command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_executor_job(self.alarm_arm_night, code)

    def alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        raise NotImplementedError()

    def async_alarm_trigger(self, code=None):
        """Send alarm trigger command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_executor_job(self.alarm_trigger, code)

    def alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command."""
        raise NotImplementedError()

    def async_alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_executor_job(
            self.alarm_arm_custom_bypass, code)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by
        }
        return state_attr

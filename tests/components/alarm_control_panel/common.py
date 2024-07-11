"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.alarm_control_panel import (
    DOMAIN,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)

from tests.common import MockEntity


async def async_alarm_disarm(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_DISARM, data, blocking=True)


async def async_alarm_arm_home(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_HOME, data, blocking=True)


async def async_alarm_arm_away(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_AWAY, data, blocking=True)


async def async_alarm_arm_night(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_NIGHT, data, blocking=True)


async def async_alarm_arm_vacation(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for vacation mode."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, SERVICE_ALARM_ARM_VACATION, data, blocking=True
    )


async def async_alarm_trigger(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_TRIGGER, data, blocking=True)


async def async_alarm_arm_custom_bypass(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, SERVICE_ALARM_ARM_CUSTOM_BYPASS, data, blocking=True
    )


class MockAlarm(MockEntity, AlarmControlPanelEntity):
    """Mock Alarm control panel class."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.TRIGGER
        | AlarmControlPanelEntityFeature.ARM_VACATION
    )

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._handle("code_arm_required")

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._attr_state = STATE_ALARM_ARMED_AWAY
        self.schedule_update_ha_state()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._attr_state = STATE_ALARM_ARMED_HOME
        self.schedule_update_ha_state()

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self._attr_state = STATE_ALARM_ARMED_NIGHT
        self.schedule_update_ha_state()

    def alarm_arm_vacation(self, code=None):
        """Send arm night command."""
        self._attr_state = STATE_ALARM_ARMED_VACATION
        self.schedule_update_ha_state()

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if code == "1234":
            self._attr_state = STATE_ALARM_DISARMED
            self.schedule_update_ha_state()

    def alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        self._attr_state = STATE_ALARM_TRIGGERED
        self.schedule_update_ha_state()

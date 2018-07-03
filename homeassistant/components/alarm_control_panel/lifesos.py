"""
Support for LifeSOS alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.lifesos/
"""
import logging
import voluptuous as vol

from homeassistant.components import alarm_control_panel as acp
from homeassistant.components.lifesos import (
    LifeSOSDevice, SIGNAL_EVENT, SIGNAL_PROPERTIES_CHANGED, DATA_BASEUNIT,
    DATA_ALARM)
from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, CONF_CODE, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_UNKNOWN,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED, ATTR_ENTITY_ID)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lifesos']

ATTR_ENTRY_DELAY = 'entry_delay'
ATTR_EXIT_DELAY = 'exit_delay'
ATTR_OPERATION_MODE = 'operation_mode'

EVENT_CLEARED_STATUS = 'lifesos_cleared_status'

ICON = 'mdi:security'

SERVICE_ALARM_MONITOR = 'lifesos_alarm_monitor'
SERVICE_CLEAR_STATUS = 'lifesos_clear_status'

SERVICE_SCHEMA_ALARM_MONITOR = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_CODE):
        vol.All(cv.string, vol.Length(min=1, max=8)),
})
SERVICE_SCHEMA_CLEAR_STATUS = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_CODE):
        vol.All(cv.string, vol.Length(min=1, max=8)),
})


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Perform the setup for LifeSOS alarm panels."""

    alarm = LifeSOSAlarm(
        hass.data[DATA_BASEUNIT],
        discovery_info[CONF_NAME])
    async_add_devices([alarm])

    async def async_alarm_monitor(service):
        """Clear the alarm/warning LEDs on base unit and stop siren."""
        if alarm.entity_id in service.data.get(CONF_ENTITY_ID):
            await alarm.async_alarm_monitor(code=service.data.get(CONF_CODE))

    async def async_clear_status(service):
        """Clear the alarm/warning LEDs on base unit and stop siren."""
        if alarm.entity_id in service.data.get(CONF_ENTITY_ID):
            await alarm.async_clear_status(code=service.data.get(CONF_CODE))

    hass.services.async_register(
        acp.DOMAIN, SERVICE_ALARM_MONITOR, async_alarm_monitor,
        schema=SERVICE_SCHEMA_ALARM_MONITOR)
    hass.services.async_register(
        acp.DOMAIN, SERVICE_CLEAR_STATUS, async_clear_status,
        schema=SERVICE_SCHEMA_CLEAR_STATUS)

    hass.data[DATA_ALARM] = alarm

    return True


class LifeSOSAlarm(LifeSOSDevice, acp.AlarmControlPanel):
    """Representation of a LifeSOS alarm panel."""

    def __init__(self, baseunit, name):
        super().__init__(baseunit, name)
        self._state = STATE_UNKNOWN

    @property
    def available(self):
        """Return True if device is available."""
        return self._baseunit.is_connected

    @property
    def code_format(self):
        """Password may be blank, or up to a maximum of 8 digits."""
        if self._baseunit.password == '':
            return None
        return 'Number'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_EXIT_DELAY: self._baseunit.exit_delay,
            ATTR_ENTRY_DELAY: self._baseunit.entry_delay,
            ATTR_OPERATION_MODE: str(self._baseunit.operation_mode),
        }

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_EVENT, self.handle_event)
        async_dispatcher_connect(
            self.hass, SIGNAL_PROPERTIES_CHANGED,
            self.handle_properties_changed)

    @callback
    def handle_event(self, contact_id):
        """When an Alarm event is received, set the Triggered state."""
        from lifesospy.enums import ContactIDEventCategory as EventCategory

        do_update = False
        if contact_id.event_category == EventCategory.Alarm:
            self._state = STATE_ALARM_TRIGGERED
            do_update = True
        if do_update:
            self.async_schedule_update_ha_state()

    @callback
    def handle_properties_changed(self, changes):
        """Update the HA state when base unit state changes, and notify HA
        we have updated state and device state attributes."""
        from lifesospy.baseunit import BaseUnit

        for change in changes:
            if change.name == BaseUnit.PROP_STATE:
                self._state = self._baseunit_state_to_ha_state(
                    change.new_value)

        self.async_schedule_update_ha_state()

    async def async_alarm_disarm(self, code=None):
        """Set operation mode to Disarm."""
        from lifesospy.enums import OperationMode
        if code is None:
            code = ''
        await self._baseunit.async_set_operation_mode(
            OperationMode.Disarm, password=code)

    async def async_alarm_arm_home(self, code=None):
        """Set operation mode to Home."""
        from lifesospy.enums import OperationMode
        if code is None:
            code = ''
        await self._baseunit.async_set_operation_mode(
            OperationMode.Home, password=code)

    async def async_alarm_arm_away(self, code=None):
        """Set operation mode to Away."""
        from lifesospy.enums import OperationMode
        if code is None:
            code = ''
        await self._baseunit.async_set_operation_mode(
            OperationMode.Away, password=code)

    async def async_alarm_monitor(self, code=None):
        """Set operation mode to Monitor."""
        from lifesospy.enums import OperationMode
        if code is None:
            code = ''
        await self._baseunit.async_set_operation_mode(
            OperationMode.Monitor, password=code)

    async def async_clear_status(self, code=None):
        """Clear the alarm/warning LEDs on base unit and stop siren."""
        if code is None:
            code = ''
        await self._baseunit.async_clear_status(password=code)
        _LOGGER.info("Alarm panel status was cleared.")

        # Restore HA state to current base unit state if we were triggered
        if self._state == STATE_ALARM_TRIGGERED:
            self._state = self._baseunit_state_to_ha_state(
                self._baseunit.state)
            self.async_schedule_update_ha_state()

        # Make clearing of status available for automation; eg. to reset
        # any lights or other devices activated by automation on alarm
        self.hass.bus.async_fire(EVENT_CLEARED_STATUS, {
            ATTR_ENTITY_ID: self.entity_id})

    @classmethod
    def _baseunit_state_to_ha_state(cls, baseunit_state):
        from lifesospy.enums import BaseUnitState

        if baseunit_state == BaseUnitState.Disarm:
            return STATE_ALARM_DISARMED
        elif baseunit_state == BaseUnitState.Home:
            return STATE_ALARM_ARMED_HOME
        elif baseunit_state == BaseUnitState.Away:
            return STATE_ALARM_ARMED_AWAY
        elif baseunit_state == BaseUnitState.Monitor:
            # Monitor is essentially like Disarm, but instead of
            # ignoring messages from sensors, it logs them as events
            # on the base unit
            return STATE_ALARM_DISARMED
        elif baseunit_state in {BaseUnitState.AwayExitDelay,
                                BaseUnitState.AwayEntryDelay}:
            return STATE_ALARM_PENDING

        return STATE_UNKNOWN

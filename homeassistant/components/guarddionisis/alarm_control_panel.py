"""Interfaces with  alarm control panels."""
import logging


import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)
from homeassistant.components.guarddionisis.util.util import DBAccess
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_DAY,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "guarddionisis"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ID): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a nightwatvhman control panel."""
    name = config.get(CONF_NAME)
    id = config.get(CONF_ID)
    guard = GuardAlarmEntity(hass, name, id)
    async_add_entities([guard])



class GuardAlarmEntity(alarm.AlarmControlPanelEntity):
    """Representation of an Alarm.com status."""

    def __init__(self, hass, name,id):
        """Initialize the Alarm.com status."""
        self.theDB = DBAccess('/home/dionisis/Database/TrackedObjectsDim.db')
        _LOGGER.debug("Setting up dionisisalarm...")
        self._hass = hass
        self._name = name
        self._id = id
        #self._websession = async_get_clientsession(self._hass)
        self._state = self.theDB.getAlarmState(id)

        #self._alarm = alarmDionisis(hass, name)

    # async def async_login(self):
    #     """Login to Alarm.com."""
    #     await self._alarm.async_login()

    async def async_update(self):
        """Fetch the latest state."""
        #await self._alarm.async_update()
        return self.state

    @property
    def name(self):
        """Return the name of the alarm."""
        return self._name

    @property
    def state(self):
        """Return the state of the alarm."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT | SUPPORT_ALARM_TRIGGER

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if await self.theDB.Disarm(self._id):
            self._state = STATE_ALARM_DISARMED
            await self.theDB.setAlarmState(self._id, self._state)

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if await self.theDB.ArmHome(self._id):
            self._state = STATE_ALARM_ARMED_HOME
            await self.theDB.setAlarmState(self._id, self._state)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if await self.theDB.ArmAway(self._id):
            self._state = STATE_ALARM_ARMED_AWAY
            await self.theDB.setAlarmState(self._id, self._state)

    async def async_alarm_arm_night(self, code=None):
        if await self.theDB.ArmNight(self._id):
            self._state = STATE_ALARM_ARMED_NIGHT
            await self.theDB.setAlarmState(self._id, self._state)

    async def async_alarm_trigger(self, code=None):
        if await self.theDB.Disarm(self._id): #for now
            self._state = STATE_ALARM_TRIGGERED
            await self.theDB.setAlarmState(self._id, self._state)

    async def async_alarm_day(self, code=None):
        if await self.theDB.ArmDay(self._id): #for now
            self._state = STATE_ALARM_ARMED_DAY
            await self.theDB.setAlarmState(self._id, self._state)
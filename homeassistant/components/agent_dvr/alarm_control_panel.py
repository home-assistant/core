"""Support for Agent Alarm Control Panels."""
import logging

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA,
    AlarmControlPanel,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
import homeassistant.helpers.config_validation as cv

from .const import ATTRIBUTION, CONNECTION, DOMAIN as AGENT_DOMAIN

_LOGGER = logging.getLogger(__name__)

ARMED = "armed"

DISARMED = "disarmed"

ICON = "mdi:security"

CONF_HOME_MODE_NAME = "home"
CONF_AWAY_MODE_NAME = "away"
CONF_NIGHT_MODE_NAME = "night"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOME_MODE_NAME, default=ARMED): cv.string,
        vol.Optional(CONF_AWAY_MODE_NAME, default=ARMED): cv.string,
        vol.Optional(CONF_NIGHT_MODE_NAME, default=ARMED): cv.string,
    }
)


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the Agent DVR Alarm Control Panels."""
    panels = []
    server = hass.data[AGENT_DOMAIN][config_entry.entry_id][CONNECTION]
    panels.append(AgentBaseStation(server))

    async_add_entities(panels)
    return True


class AgentBaseStation(AlarmControlPanel):
    """Representation of an Agent Alarm Control Panel."""

    def __init__(self, server):
        """Initialize the alarm control panel."""
        self._state = None
        self.server = server
        self._uniqueid = f"{server.unique}_CP"
        self._name = server.name

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_NIGHT

    @property
    def device_info(self):
        """Return the device info for adding the entity to the agent object."""
        return {"identifiers": {(AGENT_DOMAIN, self.server.unique)}}

    async def async_update(self):
        """Update the state of the device."""
        await self.server.update()
        armed = self.server.is_armed
        state = self._state
        if armed is not None:
            if armed:
                prof = (await self.server.get_active_profile()).lower()
                self._state = STATE_ALARM_ARMED_AWAY
                if prof == CONF_HOME_MODE_NAME:
                    self._state = STATE_ALARM_ARMED_HOME
                if prof == CONF_NIGHT_MODE_NAME:
                    self._state = STATE_ALARM_ARMED_NIGHT
            else:
                self._state = STATE_ALARM_DISARMED
        else:
            self._state = None

        if state != self._state:
            self.async_schedule_update_ha_state(True)

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self.server.disarm()
        self._state = STATE_ALARM_DISARMED

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command. Uses custom mode."""
        await self.server.arm()
        await self.server.set_active_profile(CONF_AWAY_MODE_NAME)
        self._state = STATE_ALARM_ARMED_AWAY

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command. Uses custom mode."""
        await self.server.arm()
        await self.server.set_active_profile(CONF_HOME_MODE_NAME)
        self._state = STATE_ALARM_ARMED_HOME

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command. Uses custom mode."""
        await self.server.arm()
        await self.server.set_active_profile(CONF_NIGHT_MODE_NAME)
        self._state = STATE_ALARM_ARMED_NIGHT

    @property
    def should_poll(self) -> bool:
        """Update the state periodically."""
        return True

    @property
    def name(self):
        """Return the name of the base station."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device_id": self.server.unique,
        }

    @property
    def available(self) -> bool:
        """Device available."""
        return self.server.is_available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._uniqueid

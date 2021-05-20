"""Support for Agent DVR Alarm Control Panels."""
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)

from .const import CONNECTION, DOMAIN as AGENT_DOMAIN

ICON = "mdi:security"

CONF_HOME_MODE_NAME = "home"
CONF_AWAY_MODE_NAME = "away"
CONF_NIGHT_MODE_NAME = "night"

CONST_ALARM_CONTROL_PANEL_NAME = "Alarm Panel"


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the Agent DVR Alarm Control Panels."""
    async_add_entities(
        [AgentBaseStation(hass.data[AGENT_DOMAIN][config_entry.entry_id][CONNECTION])]
    )


class AgentBaseStation(AlarmControlPanelEntity):
    """Representation of an Agent DVR Alarm Control Panel."""

    def __init__(self, client):
        """Initialize the alarm control panel."""
        self._state = None
        self._client = client
        self._unique_id = f"{client.unique}_CP"
        name = CONST_ALARM_CONTROL_PANEL_NAME
        self._name = name = f"{client.name} {name}"

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
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    @property
    def device_info(self):
        """Return the device info for adding the entity to the agent object."""
        return {
            "identifiers": {(AGENT_DOMAIN, self._client.unique)},
            "manufacturer": "Agent",
            "model": CONST_ALARM_CONTROL_PANEL_NAME,
            "sw_version": self._client.version,
        }

    async def async_update(self):
        """Update the state of the device."""
        await self._client.update()
        armed = self._client.is_armed
        if armed is None:
            self._state = None
            return
        if armed:
            prof = (await self._client.get_active_profile()).lower()
            self._state = STATE_ALARM_ARMED_AWAY
            if prof == CONF_HOME_MODE_NAME:
                self._state = STATE_ALARM_ARMED_HOME
            elif prof == CONF_NIGHT_MODE_NAME:
                self._state = STATE_ALARM_ARMED_NIGHT
        else:
            self._state = STATE_ALARM_DISARMED

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self._client.disarm()
        self._state = STATE_ALARM_DISARMED

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_AWAY_MODE_NAME)
        self._state = STATE_ALARM_ARMED_AWAY

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_HOME_MODE_NAME)
        self._state = STATE_ALARM_ARMED_HOME

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_NIGHT_MODE_NAME)
        self._state = STATE_ALARM_ARMED_NIGHT

    @property
    def name(self):
        """Return the name of the base station."""
        return self._name

    @property
    def available(self) -> bool:
        """Device available."""
        return self._client.is_available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

"""Support for Agent DVR Alarm Control Panels."""

from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONNECTION, DOMAIN as AGENT_DOMAIN

CONF_HOME_MODE_NAME = "home"
CONF_AWAY_MODE_NAME = "away"
CONF_NIGHT_MODE_NAME = "night"

CONST_ALARM_CONTROL_PANEL_NAME = "Alarm Panel"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Agent DVR Alarm Control Panels."""
    async_add_entities(
        [AgentBaseStation(hass.data[AGENT_DOMAIN][config_entry.entry_id][CONNECTION])]
    )


class AgentBaseStation(AlarmControlPanelEntity):
    """Representation of an Agent DVR Alarm Control Panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, client):
        """Initialize the alarm control panel."""
        self._client = client
        self._attr_unique_id = f"{client.unique}_CP"
        self._attr_device_info = DeviceInfo(
            identifiers={(AGENT_DOMAIN, client.unique)},
            name=f"{client.name} {CONST_ALARM_CONTROL_PANEL_NAME}",
            manufacturer="Agent",
            model=CONST_ALARM_CONTROL_PANEL_NAME,
            sw_version=client.version,
        )

    async def async_update(self) -> None:
        """Update the state of the device."""
        await self._client.update()
        self._attr_available = self._client.is_available
        armed = self._client.is_armed
        if armed is None:
            self._attr_state = None
            return
        if armed:
            prof = (await self._client.get_active_profile()).lower()
            self._attr_state = STATE_ALARM_ARMED_AWAY
            if prof == CONF_HOME_MODE_NAME:
                self._attr_state = STATE_ALARM_ARMED_HOME
            elif prof == CONF_NIGHT_MODE_NAME:
                self._attr_state = STATE_ALARM_ARMED_NIGHT
        else:
            self._attr_state = STATE_ALARM_DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._client.disarm()
        self._attr_state = STATE_ALARM_DISARMED

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_AWAY_MODE_NAME)
        self._attr_state = STATE_ALARM_ARMED_AWAY

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_HOME_MODE_NAME)
        self._attr_state = STATE_ALARM_ARMED_HOME

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command. Uses custom mode."""
        await self._client.arm()
        await self._client.set_active_profile(CONF_NIGHT_MODE_NAME)
        self._attr_state = STATE_ALARM_ARMED_NIGHT

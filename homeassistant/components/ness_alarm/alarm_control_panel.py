"""Support for Ness D8X/D16X alarm panel."""

from __future__ import annotations

import logging

from nessclient import ArmingMode, ArmingState, Client

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_NESS, SIGNAL_ARMING_STATE_CHANGED

_LOGGER = logging.getLogger(__name__)

ARMING_MODE_TO_STATE = {
    ArmingMode.ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    ArmingMode.ARMED_HOME: STATE_ALARM_ARMED_HOME,
    ArmingMode.ARMED_DAY: STATE_ALARM_ARMED_AWAY,  # no applicable state, fallback to away
    ArmingMode.ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
    ArmingMode.ARMED_VACATION: STATE_ALARM_ARMED_VACATION,
    ArmingMode.ARMED_HIGHEST: STATE_ALARM_ARMED_AWAY,  # no applicable state, fallback to away
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ness Alarm alarm control panel devices."""
    if discovery_info is None:
        return

    device = NessAlarmPanel(hass.data[DATA_NESS], "Alarm Panel")
    async_add_entities([device])


class NessAlarmPanel(alarm.AlarmControlPanelEntity):
    """Representation of a Ness alarm panel."""

    _attr_code_format = alarm.CodeFormat.NUMBER
    _attr_should_poll = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(self, client: Client, name: str) -> None:
        """Initialize the alarm panel."""
        self._client = client
        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ARMING_STATE_CHANGED, self._handle_arming_state_change
            )
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._client.disarm(code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._client.arm_away(code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._client.arm_home(code)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send trigger/panic command."""
        await self._client.panic(code)

    @callback
    def _handle_arming_state_change(
        self, arming_state: ArmingState, arming_mode: ArmingMode | None
    ) -> None:
        """Handle arming state update."""

        if arming_state == ArmingState.UNKNOWN:
            self._attr_state = None
        elif arming_state == ArmingState.DISARMED:
            self._attr_state = STATE_ALARM_DISARMED
        elif arming_state in (ArmingState.ARMING, ArmingState.EXIT_DELAY):
            self._attr_state = STATE_ALARM_ARMING
        elif arming_state == ArmingState.ARMED:
            self._attr_state = ARMING_MODE_TO_STATE.get(
                arming_mode, STATE_ALARM_ARMED_AWAY
            )
        elif arming_state == ArmingState.ENTRY_DELAY:
            self._attr_state = STATE_ALARM_PENDING
        elif arming_state == ArmingState.TRIGGERED:
            self._attr_state = STATE_ALARM_TRIGGERED
        else:
            _LOGGER.warning("Unhandled arming state: %s", arming_state)

        self.async_write_ha_state()

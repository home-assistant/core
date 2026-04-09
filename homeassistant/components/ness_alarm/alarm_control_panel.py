"""Support for Ness D8X/D16X alarm panel."""

from __future__ import annotations

import logging

from nessclient import ArmingMode, ArmingState, Client

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SIGNAL_ARMING_STATE_CHANGED, NessAlarmConfigEntry
from .const import CONF_SHOW_HOME_MODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

ARMING_MODE_TO_STATE = {
    ArmingMode.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    ArmingMode.ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
    ArmingMode.ARMED_DAY: AlarmControlPanelState.ARMED_AWAY,  # no applicable state, fallback to away
    ArmingMode.ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
    ArmingMode.ARMED_VACATION: AlarmControlPanelState.ARMED_VACATION,
    ArmingMode.ARMED_HIGHEST: AlarmControlPanelState.ARMED_AWAY,  # no applicable state, fallback to away
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NessAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ness Alarm alarm control panel from config entry."""
    client = entry.runtime_data
    show_home_mode = entry.options.get(CONF_SHOW_HOME_MODE, True)

    async_add_entities(
        [NessAlarmPanel(client, entry.entry_id, show_home_mode)],
    )


class NessAlarmPanel(AlarmControlPanelEntity):
    """Representation of a Ness alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_should_poll = False

    def __init__(self, client: Client, entry_id: str, show_home_mode: bool) -> None:
        """Initialize the alarm panel."""
        self._client = client
        self._attr_name = "Alarm Panel"
        self._attr_unique_id = f"{entry_id}_alarm_panel"
        self._attr_device_info = DeviceInfo(
            name="Alarm Panel",
            identifiers={(DOMAIN, f"{entry_id}_alarm_panel")},
        )
        features = (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.TRIGGER
        )
        if show_home_mode:
            features |= AlarmControlPanelEntityFeature.ARM_HOME
        self._attr_supported_features = features

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
            self._attr_alarm_state = None
        elif arming_state == ArmingState.DISARMED:
            self._attr_alarm_state = AlarmControlPanelState.DISARMED
        elif arming_state in (ArmingState.ARMING, ArmingState.EXIT_DELAY):
            self._attr_alarm_state = AlarmControlPanelState.ARMING
        elif arming_state == ArmingState.ARMED:
            self._attr_alarm_state = ARMING_MODE_TO_STATE.get(
                arming_mode, AlarmControlPanelState.ARMED_AWAY
            )
        elif arming_state == ArmingState.ENTRY_DELAY:
            self._attr_alarm_state = AlarmControlPanelState.PENDING
        elif arming_state == ArmingState.TRIGGERED:
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
        else:
            _LOGGER.warning("Unhandled arming state: %s", arming_state)

        self.async_write_ha_state()

"""Support for Ness alarm control panel."""

from __future__ import annotations

import logging

from nessclient import ArmingMode, ArmingState

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CONF_SUPPORT_HOME_ARM, SIGNAL_ARMING_STATE_CHANGED

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
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ness alarm control panel from a config entry."""

    data = config_entry.runtime_data
    client = data["client"]
    config = data["config"]

    entities = []

    support_home_arm = config.get(CONF_SUPPORT_HOME_ARM, True)
    entities.append(
        NessAlarmPanel(
            client,
            1,
            "Alarm Panel",
            support_home_arm,
            config_entry.entry_id,
        )
    )

    async_add_entities(entities)


class NessAlarmPanel(AlarmControlPanelEntity):
    """Representation of a Ness alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_should_poll = False

    def __init__(
        self,
        client,
        partition_id: int,
        name: str,
        support_home_arm: bool,
        entry_id: str,
    ) -> None:
        """Initialize the alarm panel."""
        self._client = client
        self._partition_id = partition_id
        self._attr_name = name
        self._entry_id = entry_id
        self._support_home_arm = support_home_arm

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ARMING_STATE_CHANGED,
                self._handle_arming_state_change,
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
        if self._support_home_arm:
            await self._client.arm_home(code)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command (panic)."""
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

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry_id}_partition_{self._partition_id}"

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        features = (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.TRIGGER
        )
        if self._support_home_arm:
            features |= AlarmControlPanelEntityFeature.ARM_HOME
        return features

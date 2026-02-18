"""Support for Satel Integra alarm, using ETHM module."""

from __future__ import annotations

import asyncio
import logging

from satel_integra.satel_integra import AlarmState

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ARM_HOME_MODE, CONF_PARTITION_NUMBER, SUBENTRY_TYPE_PARTITION
from .coordinator import SatelConfigEntry, SatelIntegraPartitionsCoordinator
from .entity import SatelIntegraEntity

ALARM_STATE_MAP = {
    AlarmState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
    AlarmState.TRIGGERED_FIRE: AlarmControlPanelState.TRIGGERED,
    AlarmState.ENTRY_TIME: AlarmControlPanelState.PENDING,
    AlarmState.ARMED_MODE3: AlarmControlPanelState.ARMED_HOME,
    AlarmState.ARMED_MODE2: AlarmControlPanelState.ARMED_HOME,
    AlarmState.ARMED_MODE1: AlarmControlPanelState.ARMED_HOME,
    AlarmState.ARMED_MODE0: AlarmControlPanelState.ARMED_AWAY,
    AlarmState.EXIT_COUNTDOWN_OVER_10: AlarmControlPanelState.ARMING,
    AlarmState.EXIT_COUNTDOWN_UNDER_10: AlarmControlPanelState.ARMING,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up for Satel Integra alarm panels."""

    runtime_data = config_entry.runtime_data

    partition_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_PARTITION,
        config_entry.subentries.values(),
    )

    for subentry in partition_subentries:
        partition_num: int = subentry.data[CONF_PARTITION_NUMBER]
        arm_home_mode: int = subentry.data[CONF_ARM_HOME_MODE]

        async_add_entities(
            [
                SatelIntegraAlarmPanel(
                    runtime_data.coordinator_partitions,
                    config_entry.entry_id,
                    subentry,
                    partition_num,
                    arm_home_mode,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraAlarmPanel(
    SatelIntegraEntity[SatelIntegraPartitionsCoordinator], AlarmControlPanelEntity
):
    """Representation of a Satel Integra-based alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(
        self,
        coordinator: SatelIntegraPartitionsCoordinator,
        config_entry_id: str,
        subentry: ConfigSubentry,
        device_number: int,
        arm_home_mode: int,
    ) -> None:
        """Initialize the alarm panel."""
        super().__init__(
            coordinator,
            config_entry_id,
            subentry,
            device_number,
        )

        self._arm_home_mode = arm_home_mode

        self._attr_alarm_state = self._read_alarm_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_alarm_state = self._read_alarm_state()
        self.async_write_ha_state()

    def _read_alarm_state(self) -> AlarmControlPanelState | None:
        """Read current status of the alarm and translate it into HA status."""

        if not self._controller.connected:
            _LOGGER.debug("Alarm panel not connected")
            return None

        for satel_state, ha_state in ALARM_STATE_MAP.items():
            if (
                satel_state in self.coordinator.data
                and self._device_number in self.coordinator.data[satel_state]
            ):
                return ha_state

        return AlarmControlPanelState.DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not code:
            _LOGGER.debug("Code was empty or None")
            return

        clear_alarm_necessary = (
            self._attr_alarm_state == AlarmControlPanelState.TRIGGERED
        )

        await self._controller.disarm(code, [self._device_number])

        if clear_alarm_necessary:
            # Wait 1s before clearing the alarm
            await asyncio.sleep(1)
            await self._controller.clear_alarm(code, [self._device_number])

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""

        if code:
            await self._controller.arm(code, [self._device_number])

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""

        if code:
            await self._controller.arm(code, [self._device_number], self._arm_home_mode)

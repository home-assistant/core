"""Support for Satel Integra alarm, using ETHM module."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
import logging

from satel_integra.satel_integra import AlarmState

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ARM_HOME_MODE,
    CONF_PARTITION_NUMBER,
    SIGNAL_PANEL_MESSAGE,
    SUBENTRY_TYPE_PARTITION,
    SatelConfigEntry,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up for Satel Integra alarm panels."""

    controller = config_entry.runtime_data

    partition_subentries = filter(
        lambda entry: entry.subentry_type == SUBENTRY_TYPE_PARTITION,
        config_entry.subentries.values(),
    )

    for subentry in partition_subentries:
        partition_num = subentry.data[CONF_PARTITION_NUMBER]
        zone_name = subentry.data[CONF_NAME]
        arm_home_mode = subentry.data[CONF_ARM_HOME_MODE]

        async_add_entities(
            [
                SatelIntegraAlarmPanel(
                    controller,
                    zone_name,
                    arm_home_mode,
                    partition_num,
                    config_entry.entry_id,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraAlarmPanel(AlarmControlPanelEntity):
    """Representation of an AlarmDecoder-based alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_should_poll = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(
        self, controller, name, arm_home_mode, partition_id, config_entry_id
    ) -> None:
        """Initialize the alarm panel."""
        self._attr_name = name
        self._attr_unique_id = f"{config_entry_id}_alarm_panel_{partition_id}"
        self._arm_home_mode = arm_home_mode
        self._partition_id = partition_id
        self._satel = controller

    async def async_added_to_hass(self) -> None:
        """Update alarm status and register callbacks for future updates."""
        _LOGGER.debug("Starts listening for panel messages")
        self._update_alarm_status()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PANEL_MESSAGE, self._update_alarm_status
            )
        )

    @callback
    def _update_alarm_status(self):
        """Handle alarm status update."""
        state = self._read_alarm_state()
        _LOGGER.debug("Got status update, current status: %s", state)
        if state != self._attr_alarm_state:
            self._attr_alarm_state = state
            self.async_write_ha_state()
        else:
            _LOGGER.debug("Ignoring alarm status message, same state")

    def _read_alarm_state(self):
        """Read current status of the alarm and translate it into HA status."""

        # Default - disarmed:
        hass_alarm_status = AlarmControlPanelState.DISARMED

        if not self._satel.connected:
            return None

        state_map = OrderedDict(
            [
                (AlarmState.TRIGGERED, AlarmControlPanelState.TRIGGERED),
                (AlarmState.TRIGGERED_FIRE, AlarmControlPanelState.TRIGGERED),
                (AlarmState.ENTRY_TIME, AlarmControlPanelState.PENDING),
                (AlarmState.ARMED_MODE3, AlarmControlPanelState.ARMED_HOME),
                (AlarmState.ARMED_MODE2, AlarmControlPanelState.ARMED_HOME),
                (AlarmState.ARMED_MODE1, AlarmControlPanelState.ARMED_HOME),
                (AlarmState.ARMED_MODE0, AlarmControlPanelState.ARMED_AWAY),
                (
                    AlarmState.EXIT_COUNTDOWN_OVER_10,
                    AlarmControlPanelState.PENDING,
                ),
                (
                    AlarmState.EXIT_COUNTDOWN_UNDER_10,
                    AlarmControlPanelState.PENDING,
                ),
            ]
        )
        _LOGGER.debug("State map of Satel: %s", self._satel.partition_states)

        for satel_state, ha_state in state_map.items():
            if (
                satel_state in self._satel.partition_states
                and self._partition_id in self._satel.partition_states[satel_state]
            ):
                hass_alarm_status = ha_state
                break

        return hass_alarm_status

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not code:
            _LOGGER.debug("Code was empty or None")
            return

        clear_alarm_necessary = (
            self._attr_alarm_state == AlarmControlPanelState.TRIGGERED
        )

        _LOGGER.debug("Disarming, self._attr_alarm_state: %s", self._attr_alarm_state)

        await self._satel.disarm(code, [self._partition_id])

        if clear_alarm_necessary:
            # Wait 1s before clearing the alarm
            await asyncio.sleep(1)
            await self._satel.clear_alarm(code, [self._partition_id])

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        _LOGGER.debug("Arming away")

        if code:
            await self._satel.arm(code, [self._partition_id])

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        _LOGGER.debug("Arming home")

        if code:
            await self._satel.arm(code, [self._partition_id], self._arm_home_mode)

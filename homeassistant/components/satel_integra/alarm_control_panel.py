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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_ARM_MAPPING,
    CONF_ARM_MAPPING_AWAY,
    CONF_ARM_MAPPING_HOME,
    CONF_DEVICE_PARTITIONS,
    CONF_NAME,
    CONF_ONE_ALARM_PANEL,
    CONF_ZONE_NAME,
    DATA_SATEL,
    DEFAULT_CONF_ARM_HOME_MODE,
    SIGNAL_PANEL_MESSAGE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up for Satel Integra alarm panels."""
    if not discovery_info:
        return

    configured_partitions = discovery_info[CONF_DEVICE_PARTITIONS]
    arm_mapping = discovery_info[CONF_ARM_MAPPING]
    controller = hass.data[DATA_SATEL]

    devices = []
    if discovery_info[CONF_ONE_ALARM_PANEL]:
        device = SatelIntegraAlarmPanel(
            controller,
            discovery_info[CONF_NAME],
            arm_mapping,
            list(configured_partitions.keys()),
        )
        devices.append(device)
    else:
        for partition_num, device_config_data in configured_partitions.items():
            zone_name = device_config_data[CONF_ZONE_NAME]
            device = SatelIntegraAlarmPanel(
                controller, zone_name, arm_mapping, [partition_num]
            )
            devices.append(device)

    async_add_entities(devices)


class SatelIntegraAlarmPanel(AlarmControlPanelEntity):
    """Representation of an AlarmDecoder-based alarm panel."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_should_poll = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(self, controller, name, arm_mapping, partitions):
        """Initialize the alarm panel."""
        self._attr_name = name
        self._partitions = partitions
        self._satel = controller
        self._arm_mapping = {
            AlarmControlPanelEntityFeature.ARM_HOME: arm_mapping.get(
                CONF_ARM_MAPPING_HOME, DEFAULT_CONF_ARM_HOME_MODE
            ),
            AlarmControlPanelEntityFeature.ARM_AWAY: arm_mapping.get(
                CONF_ARM_MAPPING_AWAY, DEFAULT_CONF_ARM_HOME_MODE
            ),
        }

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

        if not self._satel.connected:
            return None

        partition_states = self._satel.partition_states
        _LOGGER.debug("State map of Satel: %s", partition_states)

        TRIGGERED_STATES = [AlarmState.TRIGGERED, AlarmState.TRIGGERED_FIRE]
        for _state in TRIGGERED_STATES:
            if any(
                partition in partition_states.get(_state, [])
                for partition in self._partitions
            ):
                return AlarmControlPanelState.TRIGGERED

        COUNTDOWN_STATES = [
            AlarmState.ENTRY_TIME,
            AlarmState.EXIT_COUNTDOWN_OVER_10,
            AlarmState.EXIT_COUNTDOWN_UNDER_10,
        ]
        for _state in COUNTDOWN_STATES:
            if any(
                partition in partition_states.get(_state, [])
                for partition in self._partitions
            ):
                return AlarmControlPanelState.PENDING

        ARMED_AWAY_STATE = AlarmState(
            self._arm_mapping.get(AlarmControlPanelEntityFeature.ARM_AWAY)
        )
        if any(
            partition in partition_states.get(ARMED_AWAY_STATE, [])
            for partition in self._partitions
        ):
            return AlarmControlPanelState.ARMED_AWAY

        ARMED_HOME_STATE = AlarmState(
            self._arm_mapping.get(AlarmControlPanelEntityFeature.ARM_HOME)
        )
        if any(
            partition in partition_states.get(ARMED_HOME_STATE, [])
            for partition in self._partitions
        ):
            return AlarmControlPanelState.ARMED_HOME

        return AlarmControlPanelState.DISARMED

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not code:
            _LOGGER.debug("Code was empty or None")
            return

        clear_alarm_necessary = (
            self._attr_alarm_state == AlarmControlPanelState.TRIGGERED
        )

        _LOGGER.debug("Disarming, self._attr_alarm_state: %s", self._attr_alarm_state)

        await self._satel.disarm(code, self._partitions)

        if clear_alarm_necessary:
            # Wait 1s before clearing the alarm
            await asyncio.sleep(1)
            await self._satel.clear_alarm(code, self._partitions)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        _LOGGER.debug("Arming away")

        if code:
            await self._satel.arm(
                code,
                self._partitions,
                self._arm_mapping.get(AlarmControlPanelEntityFeature.ARM_AWAY),
            )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        _LOGGER.debug("Arming home")

        if code:
            await self._satel.arm(
                code,
                self._partitions,
                self._arm_mapping.get(AlarmControlPanelEntityFeature.ARM_HOME),
            )

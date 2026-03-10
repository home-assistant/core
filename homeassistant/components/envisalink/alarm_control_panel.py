"""Support for Envisalink-based alarm control panels (Honeywell/DSC)."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_CODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_PANEL_TYPE,
    CONF_PANIC,
    CONF_PARTITIONNAME,
    DATA_EVL,
    DOMAIN,
    PANEL_TYPE_DSC,
    PARTITION_SCHEMA,
    SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE,
)
from .entity import EnvisalinkEntity

_LOGGER = logging.getLogger(__name__)

SERVICE_ALARM_KEYPRESS = "alarm_keypress"
ATTR_KEYPRESS = "keypress"
ALARM_KEYPRESS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_KEYPRESS): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Perform the setup for Envisalink alarm panels."""
    if not discovery_info:
        return
    configured_partitions = discovery_info["partitions"]
    code = discovery_info[CONF_CODE]
    panic_type = discovery_info[CONF_PANIC]
    panel_type = discovery_info[CONF_PANEL_TYPE]

    entities = []
    for part_num in configured_partitions:
        entity_config_data = PARTITION_SCHEMA(configured_partitions[part_num])
        entity = EnvisalinkAlarm(
            hass,
            part_num,
            entity_config_data[CONF_PARTITIONNAME],
            code,
            panic_type,
            panel_type,
            hass.data[DATA_EVL].alarm_state["partition"][part_num],
            hass.data[DATA_EVL],
        )
        entities.append(entity)

    async_add_entities(entities)

    @callback
    def async_alarm_keypress_handler(service: ServiceCall) -> None:
        """Map services to methods on Alarm."""
        entity_ids = service.data[ATTR_ENTITY_ID]
        keypress = service.data[ATTR_KEYPRESS]

        target_entities = [
            entity for entity in entities if entity.entity_id in entity_ids
        ]

        for entity in target_entities:
            entity.async_alarm_keypress(keypress)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ALARM_KEYPRESS,
        async_alarm_keypress_handler,
        schema=ALARM_KEYPRESS_SCHEMA,
    )


class EnvisalinkAlarm(EnvisalinkEntity, AlarmControlPanelEntity):
    """Representation of an Envisalink-based alarm panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(
        self,
        hass,
        partition_number,
        alarm_name,
        code,
        panic_type,
        panel_type,
        info,
        controller,
    ):
        """Initialize the alarm panel."""
        self._partition_number = partition_number
        self._panic_type = panic_type
        self._panel_type = panel_type
        self._alarm_control_panel_option_default_code = code
        self._attr_code_format = CodeFormat.NUMBER if not code else None

        _LOGGER.debug("Setting up alarm: %s", alarm_name)
        super().__init__(alarm_name, info, controller)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_KEYPAD_UPDATE, self.async_update_callback
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PARTITION_UPDATE, self.async_update_callback
            )
        )

    @callback
    def async_update_callback(self, partition):
        """Update Home Assistant state, if needed."""
        if partition is None or int(partition) == self._partition_number:
            self.async_write_ha_state()

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        state = None

        if self._info["status"]["alarm"]:
            state = AlarmControlPanelState.TRIGGERED
        elif self._info["status"]["armed_zero_entry_delay"]:
            state = AlarmControlPanelState.ARMED_NIGHT
        elif self._info["status"]["armed_away"]:
            state = AlarmControlPanelState.ARMED_AWAY
        elif self._info["status"]["armed_stay"]:
            state = AlarmControlPanelState.ARMED_HOME
        elif self._info["status"]["exit_delay"]:
            state = AlarmControlPanelState.ARMING
        elif self._info["status"]["entry_delay"]:
            state = AlarmControlPanelState.PENDING
        elif self._info["status"]["alpha"]:
            state = AlarmControlPanelState.DISARMED
        return state

    async def _async_wake_panel(self) -> None:
        """Wake DSC panel from keypad blanking state before sending commands.

        DSC panels enter a low-power display-off (blanking) mode after
        inactivity. TPI arm/disarm commands sent while blanked are silently
        rejected. Sending '#' wakes the panel, equivalent to pressing # on
        the physical keypad.
        """
        if self._panel_type != PANEL_TYPE_DSC:
            return
        _LOGGER.debug("Sending '#' keypress to wake panel from possible blanking state")
        self.hass.data[DATA_EVL].keypresses_to_partition(self._partition_number, "#")
        await asyncio.sleep(1)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._async_wake_panel()
        self.hass.data[DATA_EVL].disarm_partition(code, self._partition_number)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._async_wake_panel()
        self.hass.data[DATA_EVL].arm_stay_partition(code, self._partition_number)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._async_wake_panel()
        self.hass.data[DATA_EVL].arm_away_partition(code, self._partition_number)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Alarm trigger command. Will be used to trigger a panic alarm."""
        self.hass.data[DATA_EVL].panic_alarm(self._panic_type)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self._async_wake_panel()
        self.hass.data[DATA_EVL].arm_night_partition(code, self._partition_number)

    @callback
    def async_alarm_keypress(self, keypress=None):
        """Send custom keypress."""
        if keypress:
            self.hass.data[DATA_EVL].keypresses_to_partition(
                self._partition_number, keypress
            )

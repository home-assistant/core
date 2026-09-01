"""Support for Envisalink-based alarm control panels (Honeywell/DSC)."""

import logging
from typing import Any, override

from pyenvisalink import EnvisalinkAlarmPanel
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnvisalinkConfigEntry
from .const import (
    ATTR_KEYPRESS,
    CONF_PANIC,
    CONF_PARTITION_NUMBER,
    CONF_PARTITIONNAME,
    DEFAULT_PANIC,
    SERVICE_ALARM_KEYPRESS,
    SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE,
    SUBENTRY_TYPE_PARTITION,
)
from .entity import EnvisalinkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnvisalinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Envisalink alarm control panels from a config entry."""
    controller = entry.runtime_data
    code = entry.options.get(CONF_CODE)
    panic_type = entry.options.get(CONF_PANIC, DEFAULT_PANIC)

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PARTITION):
        partition_number = subentry.data[CONF_PARTITION_NUMBER]
        entity = EnvisalinkAlarm(
            partition_number,
            subentry.data[CONF_PARTITIONNAME],
            code,
            panic_type,
            controller.alarm_state["partition"][partition_number],
            controller,
        )
        async_add_entities([entity], config_subentry_id=subentry.subentry_id)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_ALARM_KEYPRESS,
        {vol.Required(ATTR_KEYPRESS): cv.string},
        "async_alarm_keypress",
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
        partition_number: int,
        alarm_name: str,
        code: str | None,
        panic_type: str,
        info: dict[str, Any],
        controller: EnvisalinkAlarmPanel,
    ) -> None:
        """Initialize the alarm panel."""
        self._partition_number = partition_number
        self._panic_type = panic_type
        self._alarm_control_panel_option_default_code = code
        self._attr_code_format = CodeFormat.NUMBER if not code else None
        self._attr_code_arm_required = not code

        _LOGGER.debug("Setting up alarm: %s", alarm_name)
        super().__init__(alarm_name, info, controller)

    @override
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
    @override
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

    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._controller.disarm_partition(code, self._partition_number)

    @override
    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._controller.arm_stay_partition(code, self._partition_number)

    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._controller.arm_away_partition(code, self._partition_number)

    @override
    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Alarm trigger command. Will be used to trigger a panic alarm."""
        self._controller.panic_alarm(self._panic_type)

    @override
    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        self._controller.arm_night_partition(code, self._partition_number)

    async def async_alarm_keypress(self, keypress: str) -> None:
        """Send custom keypress."""
        self._controller.keypresses_to_partition(self._partition_number, keypress)

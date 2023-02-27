"""Support for Envisalink-based alarm control panels (Honeywell/DSC)."""
from __future__ import annotations

from pyenvisalink.const import PANEL_TYPE_HONEYWELL, STATE_CHANGE_PARTITION
import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CODE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HONEYWELL_ARM_NIGHT_MODE,
    CONF_PANIC,
    CONF_PARTITION_SET,
    CONF_PARTITIONNAME,
    CONF_PARTITIONS,
    DEFAULT_HONEYWELL_ARM_NIGHT_MODE,
    DEFAULT_PARTITION_SET,
    DOMAIN,
    LOGGER,
)
from .helpers import find_yaml_info, parse_range_string
from .models import EnvisalinkDevice

SERVICE_ALARM_KEYPRESS = "alarm_keypress"
ATTR_KEYPRESS = "keypress"

SERVICE_CUSTOM_FUNCTION = "invoke_custom_function"
ATTR_CUSTOM_FUNCTION = "pgm"
ATTR_CODE = "code"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CUSTOM_FUNCTION): cv.string,
        vol.Optional(ATTR_CODE): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm panel based on a config entry."""
    controller = hass.data[DOMAIN][entry.entry_id]
    code = entry.data.get(CONF_CODE)
    panic_type = entry.options.get(CONF_PANIC)
    partition_info = entry.data.get(CONF_PARTITIONS)
    partition_spec: str = entry.data.get(CONF_PARTITION_SET, DEFAULT_PARTITION_SET)
    partition_set = parse_range_string(
        partition_spec, min_val=1, max_val=controller.controller.max_partitions
    )

    arm_night_mode = None
    if controller.controller.panel_type == PANEL_TYPE_HONEYWELL:
        arm_night_mode = entry.options.get(
            CONF_HONEYWELL_ARM_NIGHT_MODE, DEFAULT_HONEYWELL_ARM_NIGHT_MODE
        )

    if partition_set is not None:
        entities = []
        for part_num in partition_set:
            part_entry = find_yaml_info(part_num, partition_info)
            entity = EnvisalinkAlarm(
                hass,
                part_num,
                part_entry,
                code,
                panic_type,
                arm_night_mode,
                controller,
            )
            entities.append(entity)

        async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_ALARM_KEYPRESS,
        {
            vol.Required(ATTR_KEYPRESS): cv.string,
        },
        "alarm_keypress",
    )

    platform.async_register_entity_service(
        SERVICE_CUSTOM_FUNCTION,
        {
            vol.Required(ATTR_CUSTOM_FUNCTION): cv.string,
            vol.Optional(ATTR_CODE): cv.string,
        },
        "invoke_custom_function",
    )


class EnvisalinkAlarm(EnvisalinkDevice, AlarmControlPanelEntity):
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
        partition_info,
        code,
        panic_type,
        arm_night_mode,
        controller,
    ):
        """Initialize the alarm panel."""
        self._partition_number = partition_number
        self._code = code
        self._panic_type = panic_type
        self._arm_night_mode = arm_night_mode
        name = f"Partition {partition_number}"
        self._attr_unique_id = f"{controller.unique_id}_{name}"

        self._attr_has_entity_name = True
        if partition_info:
            # Override the name if there is info from the YAML configuration
            if CONF_PARTITIONNAME in partition_info:
                name = f"{partition_info[CONF_PARTITIONNAME]}"
                self._attr_has_entity_name = False

        LOGGER.debug("Setting up alarm: %s", name)
        super().__init__(name, controller, STATE_CHANGE_PARTITION, partition_number)

    @property
    def code_format(self) -> CodeFormat | None:
        """Regex for code format or None if no code is required."""
        if self._code:
            return None
        return CodeFormat.NUMBER

    @property
    def _info(self):
        return self._controller.controller.alarm_state["partition"][
            self._partition_number
        ]

    @property
    def state(self) -> str:
        """Return the state of the device."""
        state = STATE_UNKNOWN

        if self._info["status"]["alarm"]:
            state = STATE_ALARM_TRIGGERED
        elif self._info["status"]["armed_zero_entry_delay"]:
            state = STATE_ALARM_ARMED_NIGHT
        elif self._info["status"]["armed_away"]:
            state = STATE_ALARM_ARMED_AWAY
        elif self._info["status"]["armed_stay"]:
            state = STATE_ALARM_ARMED_HOME
        elif self._info["status"]["exit_delay"]:
            state = STATE_ALARM_PENDING
        elif self._info["status"]["entry_delay"]:
            state = STATE_ALARM_PENDING
        elif self._info["status"]["alpha"]:
            state = STATE_ALARM_DISARMED
        return state

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if code:
            await self._controller.controller.disarm_partition(
                str(code), self._partition_number
            )
        else:
            await self._controller.controller.disarm_partition(
                str(self._code), self._partition_number
            )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if code:
            await self._controller.controller.arm_stay_partition(
                str(code), self._partition_number
            )
        else:
            await self._controller.controller.arm_stay_partition(
                str(self._code), self._partition_number
            )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if code:
            await self._controller.controller.arm_away_partition(
                str(code), self._partition_number
            )
        else:
            await self._controller.controller.arm_away_partition(
                str(self._code), self._partition_number
            )

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Alarm trigger command. Will be used to trigger a panic alarm."""
        await self._controller.controller.panic_alarm(self._panic_type)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self._controller.controller.arm_night_partition(
            str(code) if code else str(self._code),
            self._partition_number,
            self._arm_night_mode,
        )

    async def alarm_keypress(self, keypress=None):
        """Send custom keypress."""
        if keypress:
            await self._controller.controller.keypresses_to_partition(
                self._partition_number, keypress
            )

    async def invoke_custom_function(self, pgm, code=None):
        """Send custom/PGM to EVL."""
        if not code:
            code = self._code
        await self._controller.controller.command_output(
            code, self._partition_number, pgm
        )

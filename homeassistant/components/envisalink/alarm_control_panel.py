"""Support for Envisalink-based alarm control panels (Honeywell/DSC)."""
import logging

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    CONF_CODE,
    CONF_PANIC,
    CONF_PARTITIONNAME,
    DATA_EVL,
    DOMAIN,
    PARTITION_SCHEMA,
    SIGNAL_KEYPAD_UPDATE,
    SIGNAL_PARTITION_UPDATE,
    EnvisalinkDevice,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_ALARM_KEYPRESS = "alarm_keypress"
ATTR_KEYPRESS = "keypress"
ALARM_KEYPRESS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_KEYPRESS): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Perform the setup for Envisalink alarm panels."""
    configured_partitions = discovery_info["partitions"]
    code = discovery_info[CONF_CODE]
    panic_type = discovery_info[CONF_PANIC]

    devices = []
    for part_num in configured_partitions:
        device_config_data = PARTITION_SCHEMA(configured_partitions[part_num])
        device = EnvisalinkAlarm(
            hass,
            part_num,
            device_config_data[CONF_PARTITIONNAME],
            code,
            panic_type,
            hass.data[DATA_EVL].alarm_state["partition"][part_num],
            hass.data[DATA_EVL],
        )
        devices.append(device)

    async_add_entities(devices)

    @callback
    def alarm_keypress_handler(service):
        """Map services to methods on Alarm."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        keypress = service.data.get(ATTR_KEYPRESS)

        target_devices = [
            device for device in devices if device.entity_id in entity_ids
        ]

        for device in target_devices:
            device.async_alarm_keypress(keypress)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ALARM_KEYPRESS,
        alarm_keypress_handler,
        schema=ALARM_KEYPRESS_SCHEMA,
    )

    return True


class EnvisalinkAlarm(EnvisalinkDevice, AlarmControlPanelEntity):
    """Representation of an Envisalink-based alarm panel."""

    def __init__(
        self, hass, partition_number, alarm_name, code, panic_type, info, controller
    ):
        """Initialize the alarm panel."""
        self._partition_number = partition_number
        self._code = code
        self._panic_type = panic_type

        _LOGGER.debug("Setting up alarm: %s", alarm_name)
        super().__init__(alarm_name, info, controller)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_KEYPAD_UPDATE, self._update_callback
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PARTITION_UPDATE, self._update_callback
            )
        )

    @callback
    def _update_callback(self, partition):
        """Update Home Assistant state, if needed."""
        if partition is None or int(partition) == self._partition_number:
            self.async_write_ha_state()

    @property
    def code_format(self):
        """Regex for code format or None if no code is required."""
        if self._code:
            return None
        return FORMAT_NUMBER

    @property
    def state(self):
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

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return (
            SUPPORT_ALARM_ARM_HOME
            | SUPPORT_ALARM_ARM_AWAY
            | SUPPORT_ALARM_ARM_NIGHT
            | SUPPORT_ALARM_TRIGGER
        )

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if code:
            self.hass.data[DATA_EVL].disarm_partition(str(code), self._partition_number)
        else:
            self.hass.data[DATA_EVL].disarm_partition(
                str(self._code), self._partition_number
            )

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if code:
            self.hass.data[DATA_EVL].arm_stay_partition(
                str(code), self._partition_number
            )
        else:
            self.hass.data[DATA_EVL].arm_stay_partition(
                str(self._code), self._partition_number
            )

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if code:
            self.hass.data[DATA_EVL].arm_away_partition(
                str(code), self._partition_number
            )
        else:
            self.hass.data[DATA_EVL].arm_away_partition(
                str(self._code), self._partition_number
            )

    async def async_alarm_trigger(self, code=None):
        """Alarm trigger command. Will be used to trigger a panic alarm."""
        self.hass.data[DATA_EVL].panic_alarm(self._panic_type)

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        self.hass.data[DATA_EVL].arm_night_partition(
            str(code) if code else str(self._code), self._partition_number
        )

    @callback
    def async_alarm_keypress(self, keypress=None):
        """Send custom keypress."""
        if keypress:
            self.hass.data[DATA_EVL].keypresses_to_partition(
                self._partition_number, keypress
            )

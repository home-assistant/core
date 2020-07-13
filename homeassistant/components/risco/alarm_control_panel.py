"""Support for Risco alarms."""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)

from .const import DATA_RISCO, DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORTED_STATES = [
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_TRIGGERED,
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Risco alarm control panel."""
    risco = hass.data[DOMAIN][config_entry.entry_id][DATA_RISCO]
    alarm = await risco.get_state()
    entities = [RiscoAlarm(hass, risco, partition) for partition in alarm.partitions]

    async_add_entities(entities, False)


class RiscoAlarm(AlarmControlPanelEntity):
    """Representation of a Risco partition."""

    def __init__(self, hass, risco, partition):
        """Init the partition."""
        self._hass = hass
        self._risco = risco
        self._state = partition
        self._partition_id = partition.id

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.unique_id,
            "manufacturer": "Risco",
        }

    @property
    def unique_id(self):
        """Return a unique id for that partition."""
        return f"{self._risco.site_id}_{self._partition_id}"

    @property
    def state(self):
        """Return the state of the device."""
        if self._state.triggered:
            return STATE_ALARM_TRIGGERED
        if self._state.arming:
            return STATE_ALARM_ARMING
        if self._state.armed:
            return STATE_ALARM_ARMED_AWAY
        if self._state.partially_armed:
            return STATE_ALARM_ARMED_HOME
        if self._state.disarmed:
            return STATE_ALARM_DISARMED

        return STATE_UNKNOWN

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (
            SUPPORT_ALARM_ARM_HOME
            | SUPPORT_ALARM_ARM_AWAY
            | SUPPORT_ALARM_ARM_NIGHT
            | SUPPORT_ALARM_ARM_CUSTOM_BYPASS
        )

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return False

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        alarm = await self._risco.disarm(self._partition_id)
        self._state = alarm.partitions[self._partition_id]
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        alarm = await self._risco.partial_arm(self._partition_id)
        self._state = alarm.partitions[self._partition_id]
        self.async_write_ha_state()

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        alarm = await self._risco.partial_arm(self._partition_id)
        self._state = alarm.partitions[self._partition_id]
        self.async_write_ha_state()

    async def async_alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command."""
        alarm = await self._risco.partial_arm(self._partition_id)
        self._state = alarm.partitions[self._partition_id]
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        alarm = await self._risco.arm(self._partition_id)
        self._state = alarm.partitions[self._partition_id]
        self.async_write_ha_state()

    async def async_update(self):
        """Retrieve latest state."""
        alarm = await self._risco.get_state()
        self._state = alarm.partitions[self._partition_id]

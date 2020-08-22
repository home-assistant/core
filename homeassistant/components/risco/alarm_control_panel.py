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

from .const import DATA_COORDINATOR, DOMAIN

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
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    entities = [
        RiscoAlarm(hass, coordinator, partition_id)
        for partition_id in coordinator.data.partitions.keys()
    ]

    async_add_entities(entities, False)


class RiscoAlarm(AlarmControlPanelEntity):
    """Representation of a Risco partition."""

    def __init__(self, hass, coordinator, partition_id):
        """Init the partition."""
        self._hass = hass
        self._coordinator = coordinator
        self._partition_id = partition_id
        self._partition = self._coordinator.data.partitions[self._partition_id]

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    def _refresh_from_coordinator(self):
        self._partition = self._coordinator.data.partitions[self._partition_id]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._refresh_from_coordinator)
        )

    @property
    def _risco(self):
        """Return the Risco API object."""
        return self._coordinator.risco

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Risco",
        }

    @property
    def name(self):
        """Return the name of the partition."""
        return f"Risco {self._risco.site_name} Partition {self._partition_id}"

    @property
    def unique_id(self):
        """Return a unique id for that partition."""
        return f"{self._risco.site_uuid}_{self._partition_id}"

    @property
    def state(self):
        """Return the state of the device."""
        if self._partition.triggered:
            return STATE_ALARM_TRIGGERED
        if self._partition.arming:
            return STATE_ALARM_ARMING
        if self._partition.armed:
            return STATE_ALARM_ARMED_AWAY
        if self._partition.partially_armed:
            return STATE_ALARM_ARMED_HOME
        if self._partition.disarmed:
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
        await self._call_alarm_method("disarm")

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self._call_alarm_method("partial_arm")

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        await self._call_alarm_method("partial_arm")

    async def async_alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command."""
        await self._call_alarm_method("partial_arm")

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self._call_alarm_method("arm")

    async def _call_alarm_method(self, method, code=None):
        alarm = await getattr(self._risco, method)(self._partition_id)
        self._partition = alarm.partitions[self._partition_id]
        self.async_write_ha_state()

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

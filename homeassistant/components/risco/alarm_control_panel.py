"""Support for Risco alarms."""
import logging

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    CONF_PIN,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)

from .const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    DATA_COORDINATOR,
    DOMAIN,
)
from .entity import RiscoEntity

_LOGGER = logging.getLogger(__name__)

SUPPORTED_STATES = [
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_TRIGGERED,
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Risco alarm control panel."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    code = config_entry.data[CONF_PIN]
    code_arm_req = config_entry.options.get(CONF_CODE_ARM_REQUIRED, False)
    code_disarm_req = config_entry.options.get(CONF_CODE_DISARM_REQUIRED, False)
    entities = [
        RiscoAlarm(coordinator, partition_id, code, code_arm_req, code_disarm_req)
        for partition_id in coordinator.data.partitions
    ]

    async_add_entities(entities, False)


class RiscoAlarm(AlarmControlPanelEntity, RiscoEntity):
    """Representation of a Risco partition."""

    def __init__(
        self, coordinator, partition_id, code, code_arm_required, code_disarm_required
    ):
        """Init the partition."""
        super().__init__(coordinator)
        self._partition_id = partition_id
        self._partition = self._coordinator.data.partitions[self._partition_id]
        self._code = code
        self._code_arm_required = code_arm_required
        self._code_disarm_required = code_disarm_required

    def _get_data_from_coordinator(self):
        self._partition = self._coordinator.data.partitions[self._partition_id]

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

        return None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._code_arm_required

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        return FORMAT_NUMBER

    def _validate_code(self, code, state):
        """Validate given code."""
        check = code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        if self._code_disarm_required and not self._validate_code(code, "disarming"):
            return
        await self._call_alarm_method("disarm")

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        if self._code_arm_required and not self._validate_code(code, "arming home"):
            return
        await self._call_alarm_method("partial_arm")

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        if self._code_arm_required and not self._validate_code(code, "arming away"):
            return
        await self._call_alarm_method("arm")

    async def _call_alarm_method(self, method):
        alarm_obj = await getattr(self._risco, method)(self._partition_id)
        self._partition = alarm_obj.partitions[self._partition_id]
        self.async_write_ha_state()

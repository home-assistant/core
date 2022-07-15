"""Support for Risco alarms."""
from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PIN,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    CONF_HA_STATES_TO_RISCO,
    CONF_RISCO_STATES_TO_HA,
    DATA_COORDINATOR,
    DEFAULT_OPTIONS,
    DOMAIN,
    RISCO_ARM,
    RISCO_GROUPS,
    RISCO_PARTIAL_ARM,
)
from .entity import RiscoEntity

_LOGGER = logging.getLogger(__name__)

STATES_TO_SUPPORTED_FEATURES = {
    STATE_ALARM_ARMED_AWAY: AlarmControlPanelEntityFeature.ARM_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS: AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME: AlarmControlPanelEntityFeature.ARM_HOME,
    STATE_ALARM_ARMED_NIGHT: AlarmControlPanelEntityFeature.ARM_NIGHT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Risco alarm control panel."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    options = {**DEFAULT_OPTIONS, **config_entry.options}
    entities = [
        RiscoAlarm(coordinator, partition_id, config_entry.data[CONF_PIN], options)
        for partition_id in coordinator.data.partitions
    ]

    async_add_entities(entities, False)


class RiscoAlarm(AlarmControlPanelEntity, RiscoEntity):
    """Representation of a Risco partition."""

    _attr_code_format = CodeFormat.NUMBER

    def __init__(self, coordinator, partition_id, code, options):
        """Init the partition."""
        super().__init__(coordinator)
        self._partition_id = partition_id
        self._partition = self.coordinator.data.partitions[self._partition_id]
        self._code = code
        self._attr_code_arm_required = options[CONF_CODE_ARM_REQUIRED]
        self._code_disarm_required = options[CONF_CODE_DISARM_REQUIRED]
        self._risco_to_ha = options[CONF_RISCO_STATES_TO_HA]
        self._ha_to_risco = options[CONF_HA_STATES_TO_RISCO]
        self._attr_supported_features = 0
        for state in self._ha_to_risco:
            self._attr_supported_features |= STATES_TO_SUPPORTED_FEATURES[state]

    def _get_data_from_coordinator(self):
        self._partition = self.coordinator.data.partitions[self._partition_id]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="Risco",
        )

    @property
    def name(self) -> str:
        """Return the name of the partition."""
        return f"Risco {self._risco.site_name} Partition {self._partition_id}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for that partition."""
        return f"{self._risco.site_uuid}_{self._partition_id}"

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self._partition.triggered:
            return STATE_ALARM_TRIGGERED
        if self._partition.arming:
            return STATE_ALARM_ARMING
        if self._partition.disarmed:
            return STATE_ALARM_DISARMED
        if self._partition.armed:
            return self._risco_to_ha[RISCO_ARM]
        if self._partition.partially_armed:
            for group, armed in self._partition.groups.items():
                if armed:
                    return self._risco_to_ha[group]

            return self._risco_to_ha[RISCO_PARTIAL_ARM]

        return None

    def _validate_code(self, code):
        """Validate given code."""
        return code == self._code

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if self._code_disarm_required and not self._validate_code(code):
            _LOGGER.warning("Wrong code entered for disarming")
            return
        await self._call_alarm_method("disarm")

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._arm(STATE_ALARM_ARMED_HOME, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._arm(STATE_ALARM_ARMED_AWAY, code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self._arm(STATE_ALARM_ARMED_NIGHT, code)

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm custom bypass command."""
        await self._arm(STATE_ALARM_ARMED_CUSTOM_BYPASS, code)

    async def _arm(self, mode, code):
        if self.code_arm_required and not self._validate_code(code):
            _LOGGER.warning("Wrong code entered for %s", mode)
            return

        if not (risco_state := self._ha_to_risco[mode]):
            _LOGGER.warning("No mapping for mode %s", mode)
            return

        if risco_state in RISCO_GROUPS:
            await self._call_alarm_method("group_arm", risco_state)
        else:
            await self._call_alarm_method(risco_state)

    async def _call_alarm_method(self, method, *args):
        alarm = await getattr(self._risco, method)(self._partition_id, *args)
        self._partition = alarm.partitions[self._partition_id]
        self.async_write_ha_state()

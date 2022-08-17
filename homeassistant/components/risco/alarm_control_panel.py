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

from . import is_local
from .const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    CONF_HA_STATES_TO_RISCO,
    CONF_RISCO_STATES_TO_HA,
    DATA_COORDINATOR,
    DEFAULT_OPTIONS,
    DOMAIN,
    PARTITION_UPDATES,
    RISCO_ARM,
    RISCO_GROUPS,
    RISCO_PARTIAL_ARM,
    SYSTEM,
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
    options = {**DEFAULT_OPTIONS, **config_entry.options}
    if is_local(config_entry):
        partition_updates = hass.data[DOMAIN][config_entry.entry_id][PARTITION_UPDATES]
        system = hass.data[DOMAIN][config_entry.entry_id][SYSTEM]
        async_add_entities(
            RiscoLocalAlarm(
                system.id,
                partition_id,
                partition,
                partition_updates,
                config_entry.data[CONF_PIN],
                options,
            )
            for partition_id, partition in system.partitions.items()
        )
    else:
        coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
        async_add_entities(
            RiscoCloudAlarm(
                coordinator, partition_id, config_entry.data[CONF_PIN], options
            )
            for partition_id in coordinator.data.partitions
        )


class RiscoAlarm(AlarmControlPanelEntity):
    """Representation of a Risco cloud partition."""

    _attr_code_format = CodeFormat.NUMBER

    def __init__(self, partition_id, partition, code, options):
        """Init the partition."""
        self._partition_id = partition_id
        self._partition = partition
        self._code = code
        self._attr_code_arm_required = options[CONF_CODE_ARM_REQUIRED]
        self._code_disarm_required = options[CONF_CODE_DISARM_REQUIRED]
        self._risco_to_ha = options[CONF_RISCO_STATES_TO_HA]
        self._ha_to_risco = options[CONF_HA_STATES_TO_RISCO]
        self._attr_supported_features = 0
        for state in self._ha_to_risco:
            self._attr_supported_features |= STATES_TO_SUPPORTED_FEATURES[state]

    @property
    def unique_id(self) -> str:
        """Return a unique id for this partition."""
        raise NotImplementedError

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="Risco",
        )

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
        raise NotImplementedError


class RiscoCloudAlarm(RiscoEntity, RiscoAlarm):
    """Representation of a Risco partition."""

    def __init__(self, coordinator, partition_id, code, options):
        """Init the partition."""
        RiscoEntity.__init__(self, coordinator)
        RiscoAlarm.__init__(
            self, partition_id, coordinator.data.partitions[partition_id], code, options
        )
        super().__init__(coordinator)

    def _get_data_from_coordinator(self):
        self._partition = self.coordinator.data.partitions[self._partition_id]

    @property
    def name(self) -> str:
        """Return the name of the partition."""
        return f"Risco {self._risco.site_name} Partition {self._partition_id}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for that partition."""
        return f"{self._risco.site_uuid}_{self._partition_id}"

    async def _call_alarm_method(self, method, *args):
        alarm = await getattr(self._risco, method)(self._partition_id, *args)
        self._partition = alarm.partitions[self._partition_id]
        self.async_write_ha_state()


class RiscoLocalAlarm(RiscoAlarm):
    """Representation of a Risco local, partition."""

    def __init__(
        self, system_id, partition_id, partition, partition_updates, code, options
    ):
        """Init the partition."""
        super().__init__(partition_id, partition, code, options)
        self._system_id = system_id
        self._partition_updates = partition_updates

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._partition_updates[self._partition_id] = self.async_write_ha_state

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the partition."""
        return f"Risco {self._system_id} Partition {self._partition_id}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for that partition."""
        return f"{self._system_id}_{self._partition_id}_local"

    async def _call_alarm_method(self, method, *args):
        await getattr(self._partition, method)(*args)

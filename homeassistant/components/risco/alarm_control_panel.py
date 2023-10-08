"""Support for Risco alarms."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from pyrisco.common import Partition

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LocalData, RiscoDataUpdateCoordinator, is_local
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
from .entity import RiscoCloudEntity

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
        local_data: LocalData = hass.data[DOMAIN][config_entry.entry_id]
        async_add_entities(
            RiscoLocalAlarm(
                local_data.system.id,
                partition_id,
                partition,
                local_data.partition_updates,
                config_entry.data[CONF_PIN],
                options,
            )
            for partition_id, partition in local_data.system.partitions.items()
        )
    else:
        coordinator: RiscoDataUpdateCoordinator = hass.data[DOMAIN][
            config_entry.entry_id
        ][DATA_COORDINATOR]
        async_add_entities(
            RiscoCloudAlarm(
                coordinator, partition_id, config_entry.data[CONF_PIN], options
            )
            for partition_id in coordinator.data.partitions
        )


class RiscoAlarm(AlarmControlPanelEntity):
    """Representation of a Risco cloud partition."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        *,
        partition_id: int,
        partition: Partition,
        code: str,
        options: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Init the partition."""
        super().__init__(**kwargs)
        self._partition_id = partition_id
        self._partition = partition
        self._code = code
        self._attr_code_arm_required = options[CONF_CODE_ARM_REQUIRED]
        self._code_disarm_required = options[CONF_CODE_DISARM_REQUIRED]
        self._risco_to_ha = options[CONF_RISCO_STATES_TO_HA]
        self._ha_to_risco = options[CONF_HA_STATES_TO_RISCO]
        for state in self._ha_to_risco:
            self._attr_supported_features |= STATES_TO_SUPPORTED_FEATURES[state]

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

    async def _call_alarm_method(self, method: str, *args: Any) -> None:
        raise NotImplementedError


class RiscoCloudAlarm(RiscoAlarm, RiscoCloudEntity):
    """Representation of a Risco partition."""

    def __init__(
        self,
        coordinator: RiscoDataUpdateCoordinator,
        partition_id: int,
        code: str,
        options: dict[str, Any],
    ) -> None:
        """Init the partition."""
        super().__init__(
            partition_id=partition_id,
            partition=coordinator.data.partitions[partition_id],
            coordinator=coordinator,
            code=code,
            options=options,
        )
        self._attr_unique_id = f"{self._risco.site_uuid}_{partition_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=f"Risco {self._risco.site_name} Partition {partition_id}",
            manufacturer="Risco",
        )

    def _get_data_from_coordinator(self) -> None:
        self._partition = self.coordinator.data.partitions[self._partition_id]

    async def _call_alarm_method(self, method, *args):
        alarm = await getattr(self._risco, method)(self._partition_id, *args)
        self._partition = alarm.partitions[self._partition_id]
        self.async_write_ha_state()


class RiscoLocalAlarm(RiscoAlarm):
    """Representation of a Risco local, partition."""

    _attr_should_poll = False

    def __init__(
        self,
        system_id: str,
        partition_id: int,
        partition: Partition,
        partition_updates: dict[int, Callable[[], Any]],
        code: str,
        options: dict[str, Any],
    ) -> None:
        """Init the partition."""
        super().__init__(
            partition_id=partition_id, partition=partition, code=code, options=options
        )
        self._system_id = system_id
        self._partition_updates = partition_updates
        self._attr_unique_id = f"{system_id}_{partition_id}_local"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=partition.name,
            manufacturer="Risco",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._partition_updates[self._partition_id] = self.async_write_ha_state

    async def _call_alarm_method(self, method: str, *args: Any) -> None:
        await getattr(self._partition, method)(*args)

"""Support for Bosch Alarm Panel binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from bosch_alarm_mode2 import Panel
from bosch_alarm_mode2.const import ALARM_PANEL_FAULTS

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .entity import BoschAlarmAreaEntity, BoschAlarmEntity, BoschAlarmPointEntity


@dataclass(kw_only=True, frozen=True)
class BoschAlarmFaultEntityDescription(BinarySensorEntityDescription):
    """Describes Bosch Alarm sensor entity."""

    fault: int


FAULT_TYPES = [
    BoschAlarmFaultEntityDescription(
        key="panel_fault_battery_low",
        translation_key="panel_fault_battery_low",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.BATTERY_LOW,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_battery_mising",
        translation_key="panel_fault_battery_mising",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.BATTERY_MISING,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_ac_fail",
        translation_key="panel_fault_ac_fail",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.AC_FAIL,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_phone_line_failure",
        translation_key="panel_fault_phone_line_failure",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        fault=ALARM_PANEL_FAULTS.PHONE_LINE_FAILURE,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_parameter_crc_fail_in_pif",
        translation_key="panel_fault_parameter_crc_fail_in_pif",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.PARAMETER_CRC_FAIL_IN_PIF,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_communication_fail_since_rps_hang_up",
        translation_key="panel_fault_communication_fail_since_rps_hang_up",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.COMMUNICATION_FAIL_SINCE_RPS_HANG_UP,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_sdi_fail_since_rps_hang_up",
        translation_key="panel_fault_sdi_fail_since_rps_hang_up",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.SDI_FAIL_SINCE_RPS_HANG_UP,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_user_code_tamper_since_rps_hang_up",
        translation_key="panel_fault_user_code_tamper_since_rps_hang_up",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.USER_CODE_TAMPER_SINCE_RPS_HANG_UP,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_fail_to_call_rps_since_rps_hang_up",
        translation_key="panel_fault_fail_to_call_rps_since_rps_hang_up",
        entity_registry_enabled_default=False,
        fault=ALARM_PANEL_FAULTS.FAIL_TO_CALL_RPS_SINCE_RPS_HANG_UP,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_point_bus_fail_since_rps_hang_up",
        translation_key="panel_fault_point_bus_fail_since_rps_hang_up",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.POINT_BUS_FAIL_SINCE_RPS_HANG_UP,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_log_overflow",
        translation_key="panel_fault_log_overflow",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.LOG_OVERFLOW,
    ),
    BoschAlarmFaultEntityDescription(
        key="panel_fault_log_threshold",
        translation_key="panel_fault_log_threshold",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.PROBLEM,
        fault=ALARM_PANEL_FAULTS.LOG_THRESHOLD,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for alarm points and the connection status."""
    panel = config_entry.runtime_data

    entities: list[BinarySensorEntity] = [
        PointSensor(panel, point_id, config_entry.unique_id or config_entry.entry_id)
        for point_id in panel.points
    ]

    entities.extend(
        PanelFaultsSensor(
            panel,
            config_entry.unique_id or config_entry.entry_id,
            fault_type,
        )
        for fault_type in FAULT_TYPES
    )

    entities.extend(
        AreaReadyToArmSensor(
            panel, area_id, config_entry.unique_id or config_entry.entry_id, "away"
        )
        for area_id in panel.areas
    )

    entities.extend(
        AreaReadyToArmSensor(
            panel, area_id, config_entry.unique_id or config_entry.entry_id, "home"
        )
        for area_id in panel.areas
    )

    async_add_entities(entities)


PARALLEL_UPDATES = 0


class PanelFaultsSensor(BoschAlarmEntity, BinarySensorEntity):
    """A binary sensor entity for each fault type in a bosch alarm panel."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: BoschAlarmFaultEntityDescription

    def __init__(
        self,
        panel: Panel,
        unique_id: str,
        entity_description: BoschAlarmFaultEntityDescription,
    ) -> None:
        """Set up a binary sensor entity for each fault type in a bosch alarm panel."""
        super().__init__(panel, unique_id, True)
        self.entity_description = entity_description
        self._fault_type = entity_description.fault
        self._attr_unique_id = f"{unique_id}_fault_{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return if this fault has occurred."""
        return self._fault_type in self.panel.panel_faults_ids


class AreaReadyToArmSensor(BoschAlarmAreaEntity, BinarySensorEntity):
    """A binary sensor entity showing if a panel is ready to arm."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, panel: Panel, area_id: int, unique_id: str, arm_type: str
    ) -> None:
        """Set up a binary sensor entity for the arming status in a bosch alarm panel."""
        super().__init__(panel, area_id, unique_id, False, False, True)
        self.panel = panel
        self._arm_type = arm_type
        self._attr_translation_key = f"area_ready_to_arm_{arm_type}"
        self._attr_unique_id = f"{self._area_unique_id}_ready_to_arm_{arm_type}"

    @property
    def is_on(self) -> bool:
        """Return if this panel is ready to arm."""
        if self._arm_type == "away":
            return self._area.all_ready
        if self._arm_type == "home":
            return self._area.all_ready or self._area.part_ready
        return False


class PointSensor(BoschAlarmPointEntity, BinarySensorEntity):
    """A binary sensor entity for a point in a bosch alarm panel."""

    _attr_name = None

    def __init__(self, panel: Panel, point_id: int, unique_id: str) -> None:
        """Set up a binary sensor entity for a point in a bosch alarm panel."""
        super().__init__(panel, point_id, unique_id)
        self._attr_unique_id = self._point_unique_id

    @property
    def is_on(self) -> bool:
        """Return if this point sensor is on."""
        return self._point.is_open()

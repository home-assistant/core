"""Support for Bosch Alarm Panel binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from bosch_alarm_mode2 import Panel
from bosch_alarm_mode2.const import ALARM_PANEL_FAULTS

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .const import DOMAIN


@dataclass
class FaultDescription:
    """Mappings for the various faults an alarm can have."""

    state: str
    fault: int
    enabled_by_default: bool
    device_class: BinarySensorDeviceClass | None = None


fault_types = [
    FaultDescription(
        "battery_low",
        ALARM_PANEL_FAULTS.BATTERY_LOW,
        True,
        BinarySensorDeviceClass.BATTERY,
    ),
    FaultDescription(
        "battery_mising",
        ALARM_PANEL_FAULTS.BATTERY_MISING,
        True,
        BinarySensorDeviceClass.BATTERY,
    ),
    FaultDescription(
        "ac_fail", ALARM_PANEL_FAULTS.AC_FAIL, True, BinarySensorDeviceClass.PLUG
    ),
    FaultDescription(
        "phone_line_failure",
        ALARM_PANEL_FAULTS.PHONE_LINE_FAILURE,
        True,
        BinarySensorDeviceClass.CONNECTIVITY,
    ),
    FaultDescription(
        "parameter_crc_fail_in_pif", ALARM_PANEL_FAULTS.PARAMETER_CRC_FAIL_IN_PIF, False
    ),
    FaultDescription(
        "communication_fail_since_rps_hang_up",
        ALARM_PANEL_FAULTS.COMMUNICATION_FAIL_SINCE_RPS_HANG_UP,
        False,
    ),
    FaultDescription(
        "sdi_fail_since_rps_hang_up",
        ALARM_PANEL_FAULTS.SDI_FAIL_SINCE_RPS_HANG_UP,
        False,
    ),
    FaultDescription(
        "user_code_tamper_since_rps_hang_up",
        ALARM_PANEL_FAULTS.USER_CODE_TAMPER_SINCE_RPS_HANG_UP,
        False,
    ),
    FaultDescription(
        "fail_to_call_rps_since_rps_hang_up",
        ALARM_PANEL_FAULTS.FAIL_TO_CALL_RPS_SINCE_RPS_HANG_UP,
        False,
    ),
    FaultDescription(
        "point_bus_fail_since_rps_hang_up",
        ALARM_PANEL_FAULTS.POINT_BUS_FAIL_SINCE_RPS_HANG_UP,
        False,
    ),
    FaultDescription("log_overflow", ALARM_PANEL_FAULTS.LOG_OVERFLOW, True),
    FaultDescription("log_threshold", ALARM_PANEL_FAULTS.LOG_THRESHOLD, True),
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
        for fault_type in fault_types
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


class AreaReadyToArmSensor(BinarySensorEntity):
    """A binary sensor entity showing if a panel is ready to arm."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, panel: Panel, area_id: int, unique_id: str, arm_type: str
    ) -> None:
        """Set up a binary sensor entity for the arming status in a bosch alarm panel."""
        self.panel = panel
        area_unique_id = f"{unique_id}_area_{area_id}"
        self._arm_type = arm_type
        self._area = panel.areas[area_id]
        self._attr_translation_key = f"area_ready_to_arm_{arm_type}"
        self._attr_unique_id = f"{area_unique_id}_ready_to_arm_{arm_type}"
        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, area_unique_id)},
            name=self._area.name,
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
        )

    @property
    def is_on(self) -> bool:
        """Return if this panel is ready to arm."""
        if self._arm_type == "away":
            return self._area.all_ready
        if self._arm_type == "home":
            return self._area.all_ready or self._area.part_ready
        return False

    @property
    def available(self) -> bool:
        """Return if this point sensor is available."""
        return self.panel.connection_status()

    async def async_added_to_hass(self) -> None:
        """Return True if entity is available."""
        await super().async_added_to_hass()
        self._area.status_observer.attach(self.schedule_update_ha_state)
        self.panel.connection_status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity removed from hass."""
        await super().async_will_remove_from_hass()
        self._area.status_observer.attach(self.schedule_update_ha_state)
        self.panel.connection_status_observer.attach(self.schedule_update_ha_state)


class PanelFaultsSensor(BinarySensorEntity):
    """A binary sensor entity for each fault type in a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        panel: Panel,
        unique_id: str,
        fault_type: FaultDescription,
    ) -> None:
        """Set up a binary sensor entity for each fault type in a bosch alarm panel."""
        self._attr_entity_registry_enabled_default = fault_type.enabled_by_default
        self._attr_device_class = fault_type.device_class
        self.panel = panel
        self._fault_type = fault_type
        self._attr_translation_key = f"panel_fault_{fault_type.state}"
        self._attr_unique_id = f"{unique_id}_fault_{fault_type.state}"
        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=f"Bosch {panel.model}",
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
        )

    @property
    def is_on(self) -> bool:
        """Return if this fault has occurred."""
        return self._fault_type.fault in self.panel.panel_faults_ids

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.panel.connection_status()

    async def async_added_to_hass(self) -> None:
        """Run when entity attached to hass."""
        await super().async_added_to_hass()
        self.panel.connection_status_observer.attach(self.schedule_update_ha_state)
        self.panel.faults_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity removed from hass."""
        await super().async_will_remove_from_hass()
        self.panel.connection_status_observer.attach(self.schedule_update_ha_state)
        self.panel.faults_observer.attach(self.schedule_update_ha_state)


class PointSensor(BinarySensorEntity):
    """A binary sensor entity for a point in a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, panel: Panel, point_id: int, unique_id: str) -> None:
        """Set up a binary sensor entity for a point in a bosch alarm panel."""
        self.panel = panel
        self._attr_unique_id = f"{unique_id}_point_{point_id}"
        self._point = panel.points[point_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Bosch Security Systems",
            name=self._point.name,
            via_device=(DOMAIN, unique_id),
        )

    @property
    def is_on(self) -> bool:
        """Return if this point sensor is on."""
        return self._point.is_open()

    @property
    def available(self) -> bool:
        """Return if this point sensor is available."""
        return self._point.is_open() or self._point.is_normal()

    async def async_added_to_hass(self) -> None:
        """Run when entity attached to hass."""
        await super().async_added_to_hass()
        self._point.status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity removed from hass."""
        await super().async_will_remove_from_hass()
        self._point.status_observer.detach(self.schedule_update_ha_state)

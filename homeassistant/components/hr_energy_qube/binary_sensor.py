"""Binary sensor platform for Qube Heat Pump."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from python_qube_heatpump.models import QubeState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .entity import QubeEntity

PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import QubeConfigEntry
    from .coordinator import QubeCoordinator


@dataclass(frozen=True, kw_only=True)
class QubeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor entity description for Qube Heat Pump."""

    value_fn: Callable[[QubeState], bool | None]


BINARY_SENSOR_TYPES: tuple[QubeBinarySensorEntityDescription, ...] = (
    # Outputs
    QubeBinarySensorEntityDescription(
        key="source_pump",
        translation_key="source_pump",
        value_fn=lambda data: data.dout_srcpmp_val,
    ),
    QubeBinarySensorEntityDescription(
        key="user_pump",
        translation_key="user_pump",
        value_fn=lambda data: data.dout_usrpmp_val,
    ),
    QubeBinarySensorEntityDescription(
        key="four_way_valve",
        translation_key="four_way_valve",
        value_fn=lambda data: data.dout_fourwayvlv_val,
    ),
    QubeBinarySensorEntityDescription(
        key="cooling_output",
        translation_key="cooling_output",
        value_fn=lambda data: data.dout_cooling_val,
    ),
    QubeBinarySensorEntityDescription(
        key="three_way_valve",
        translation_key="three_way_valve",
        value_fn=lambda data: data.dout_threewayvlv_val,
    ),
    QubeBinarySensorEntityDescription(
        key="buffer_pump",
        translation_key="buffer_pump",
        value_fn=lambda data: data.dout_bufferpmp_val,
    ),
    QubeBinarySensorEntityDescription(
        key="heater_step_1",
        translation_key="heater_step_1",
        value_fn=lambda data: data.dout_heaterstep1_val,
    ),
    QubeBinarySensorEntityDescription(
        key="heater_step_2",
        translation_key="heater_step_2",
        value_fn=lambda data: data.dout_heaterstep2_val,
    ),
    QubeBinarySensorEntityDescription(
        key="heater_step_3",
        translation_key="heater_step_3",
        value_fn=lambda data: data.dout_heaterstep3_val,
    ),
    # System status
    QubeBinarySensorEntityDescription(
        key="keypad",
        translation_key="keypad",
        value_fn=lambda data: data.keybonoff,
    ),
    QubeBinarySensorEntityDescription(
        key="day_mode",
        translation_key="day_mode",
        value_fn=lambda data: data.daynightmode,
    ),
    # Alarms
    QubeBinarySensorEntityDescription(
        key="alarm_antilegionella_timeout",
        translation_key="alarm_antilegionella_timeout",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.al_maxtime_antileg_active,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_dhw_timeout",
        translation_key="alarm_dhw_timeout",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.al_maxtime_dhw_active,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_dewpoint",
        translation_key="alarm_dewpoint",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.al_dewpoint_active,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_supply_too_hot",
        translation_key="alarm_supply_too_hot",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.al_underfloorsafety_active,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_flow",
        translation_key="alarm_flow",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alrm_flw,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_central_heating",
        translation_key="alarm_central_heating",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.usralrms,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_cooling",
        translation_key="alarm_cooling",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.coolingalrms,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_heating",
        translation_key="alarm_heating",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.heatingalrms,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_working_hours",
        translation_key="alarm_working_hours",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarmmng_al_workinghour,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_source",
        translation_key="alarm_source",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.srsalrm,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_global",
        translation_key="alarm_global",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.glbal,
    ),
    QubeBinarySensorEntityDescription(
        key="alarm_compressor",
        translation_key="alarm_compressor",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarmmng_al_pwrplus,
    ),
    # Sensor/controller status
    QubeBinarySensorEntityDescription(
        key="room_sensor_enabled",
        translation_key="room_sensor_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.roomprb_en,
    ),
    QubeBinarySensorEntityDescription(
        key="plant_sensor_enabled",
        translation_key="plant_sensor_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.plantprb_en,
    ),
    QubeBinarySensorEntityDescription(
        key="buffer_sensor_enabled",
        translation_key="buffer_sensor_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.bufferprb_en,
    ),
    QubeBinarySensorEntityDescription(
        key="dhw_controller_enabled",
        translation_key="dhw_controller_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.en_dhwpid,
    ),
    # Demand signals
    QubeBinarySensorEntityDescription(
        key="plant_demand",
        translation_key="plant_demand",
        value_fn=lambda data: data.plantdemand,
    ),
    QubeBinarySensorEntityDescription(
        key="external_demand",
        translation_key="external_demand",
        value_fn=lambda data: data.id_demand,
    ),
    QubeBinarySensorEntityDescription(
        key="thermostat_demand",
        translation_key="thermostat_demand",
        value_fn=lambda data: data.thermostatdemand,
    ),
    # Digital inputs
    QubeBinarySensorEntityDescription(
        key="summer_mode",
        translation_key="summer_mode",
        value_fn=lambda data: data.id_summerwinter,
    ),
    QubeBinarySensorEntityDescription(
        key="dewpoint",
        translation_key="dewpoint",
        value_fn=lambda data: data.dewpoint,
    ),
    QubeBinarySensorEntityDescription(
        key="booster_security",
        translation_key="booster_security",
        value_fn=lambda data: data.boostersecurity,
    ),
    QubeBinarySensorEntityDescription(
        key="source_flow",
        translation_key="source_flow",
        value_fn=lambda data: data.srcflw,
    ),
    QubeBinarySensorEntityDescription(
        key="anti_legionella",
        translation_key="anti_legionella",
        value_fn=lambda data: data.req_antileg_1,
    ),
    # Energy
    QubeBinarySensorEntityDescription(
        key="pv_surplus",
        translation_key="pv_surplus",
        value_fn=lambda data: data.surplus_pv,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube binary sensors."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        QubeBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_TYPES
    )


class QubeBinarySensor(QubeEntity, BinarySensorEntity):
    """Qube binary sensor entity."""

    entity_description: QubeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: QubeCoordinator,
        entry: QubeConfigEntry,
        description: QubeBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}-{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)

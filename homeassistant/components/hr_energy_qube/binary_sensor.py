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
        key="dout_srcpmp_val",
        translation_key="dout_srcpmp_val",
        value_fn=lambda data: data.dout_srcpmp_val,
    ),
    QubeBinarySensorEntityDescription(
        key="dout_usrpmp_val",
        translation_key="dout_usrpmp_val",
        value_fn=lambda data: data.dout_usrpmp_val,
    ),
    QubeBinarySensorEntityDescription(
        key="dout_fourwayvlv_val",
        translation_key="dout_fourwayvlv_val",
        value_fn=lambda data: data.dout_fourwayvlv_val,
    ),
    QubeBinarySensorEntityDescription(
        key="dout_cooling_val",
        translation_key="dout_cooling_val",
        value_fn=lambda data: data.dout_cooling_val,
    ),
    QubeBinarySensorEntityDescription(
        key="dout_threewayvlv_val",
        translation_key="dout_threewayvlv_val",
        value_fn=lambda data: data.dout_threewayvlv_val,
    ),
    QubeBinarySensorEntityDescription(
        key="dout_bufferpmp_val",
        translation_key="dout_bufferpmp_val",
        value_fn=lambda data: data.dout_bufferpmp_val,
    ),
    QubeBinarySensorEntityDescription(
        key="dout_heaterstep1_val",
        translation_key="dout_heaterstep1_val",
        value_fn=lambda data: data.dout_heaterstep1_val,
    ),
    QubeBinarySensorEntityDescription(
        key="dout_heaterstep2_val",
        translation_key="dout_heaterstep2_val",
        value_fn=lambda data: data.dout_heaterstep2_val,
    ),
    QubeBinarySensorEntityDescription(
        key="dout_heaterstep3_val",
        translation_key="dout_heaterstep3_val",
        value_fn=lambda data: data.dout_heaterstep3_val,
    ),
    # System status
    QubeBinarySensorEntityDescription(
        key="keybonoff",
        translation_key="keybonoff",
        value_fn=lambda data: data.keybonoff,
    ),
    QubeBinarySensorEntityDescription(
        key="daynightmode",
        translation_key="daynightmode",
        value_fn=lambda data: data.daynightmode,
    ),
    # Alarms
    QubeBinarySensorEntityDescription(
        key="al_maxtime_antileg_active",
        translation_key="al_maxtime_antileg_active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.al_maxtime_antileg_active,
    ),
    QubeBinarySensorEntityDescription(
        key="al_maxtime_dhw_active",
        translation_key="al_maxtime_dhw_active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.al_maxtime_dhw_active,
    ),
    QubeBinarySensorEntityDescription(
        key="al_dewpoint_active",
        translation_key="al_dewpoint_active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.al_dewpoint_active,
    ),
    QubeBinarySensorEntityDescription(
        key="al_underfloorsafety_active",
        translation_key="al_underfloorsafety_active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.al_underfloorsafety_active,
    ),
    QubeBinarySensorEntityDescription(
        key="alrm_flw",
        translation_key="alrm_flw",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alrm_flw,
    ),
    QubeBinarySensorEntityDescription(
        key="usralrms",
        translation_key="usralrms",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.usralrms,
    ),
    QubeBinarySensorEntityDescription(
        key="coolingalrms",
        translation_key="coolingalrms",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.coolingalrms,
    ),
    QubeBinarySensorEntityDescription(
        key="heatingalrms",
        translation_key="heatingalrms",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.heatingalrms,
    ),
    QubeBinarySensorEntityDescription(
        key="alarmmng_al_workinghour",
        translation_key="alarmmng_al_workinghour",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarmmng_al_workinghour,
    ),
    QubeBinarySensorEntityDescription(
        key="srsalrm",
        translation_key="srsalrm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.srsalrm,
    ),
    QubeBinarySensorEntityDescription(
        key="glbal",
        translation_key="glbal",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.glbal,
    ),
    QubeBinarySensorEntityDescription(
        key="alarmmng_al_pwrplus",
        translation_key="alarmmng_al_pwrplus",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarmmng_al_pwrplus,
    ),
    # Sensor/controller status
    QubeBinarySensorEntityDescription(
        key="roomprb_en",
        translation_key="roomprb_en",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.roomprb_en,
    ),
    QubeBinarySensorEntityDescription(
        key="plantprb_en",
        translation_key="plantprb_en",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.plantprb_en,
    ),
    QubeBinarySensorEntityDescription(
        key="bufferprb_en",
        translation_key="bufferprb_en",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.bufferprb_en,
    ),
    QubeBinarySensorEntityDescription(
        key="en_dhwpid",
        translation_key="en_dhwpid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.en_dhwpid,
    ),
    # Demand signals
    QubeBinarySensorEntityDescription(
        key="plantdemand",
        translation_key="plantdemand",
        value_fn=lambda data: data.plantdemand,
    ),
    QubeBinarySensorEntityDescription(
        key="id_demand",
        translation_key="id_demand",
        value_fn=lambda data: data.id_demand,
    ),
    QubeBinarySensorEntityDescription(
        key="thermostatdemand",
        translation_key="thermostatdemand",
        value_fn=lambda data: data.thermostatdemand,
    ),
    QubeBinarySensorEntityDescription(
        key="bms_demand",
        translation_key="bms_demand",
        value_fn=lambda data: data.bms_demand,
    ),
    # Digital inputs
    QubeBinarySensorEntityDescription(
        key="id_summerwinter",
        translation_key="id_summerwinter",
        value_fn=lambda data: data.id_summerwinter,
    ),
    QubeBinarySensorEntityDescription(
        key="dewpoint",
        translation_key="dewpoint",
        value_fn=lambda data: data.dewpoint,
    ),
    QubeBinarySensorEntityDescription(
        key="boostersecurity",
        translation_key="boostersecurity",
        value_fn=lambda data: data.boostersecurity,
    ),
    QubeBinarySensorEntityDescription(
        key="srcflw",
        translation_key="srcflw",
        value_fn=lambda data: data.srcflw,
    ),
    QubeBinarySensorEntityDescription(
        key="req_antileg_1",
        translation_key="req_antileg_1",
        value_fn=lambda data: data.req_antileg_1,
    ),
    # Energy
    QubeBinarySensorEntityDescription(
        key="surplus_pv",
        translation_key="surplus_pv",
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

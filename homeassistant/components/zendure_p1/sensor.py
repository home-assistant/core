"""Support for Zendure Smart Meter P1 sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from zendure_p1 import Report

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfApparentPower, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import ZendureP1ConfigEntry
from .coordinator import ZendureP1Coordinator
from .entity import ZendureP1Entity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ZendureP1SensorEntityDescription(SensorEntityDescription):
    """Describes a Zendure Smart Meter P1 sensor."""

    value_fn: Callable[[Report], StateType]


SENSORS: tuple[ZendureP1SensorEntityDescription, ...] = (
    ZendureP1SensorEntityDescription(
        key="phase_1_apparent_power",
        translation_key="phase_1_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda report: report.a_apparent_power,
    ),
    ZendureP1SensorEntityDescription(
        key="phase_2_apparent_power",
        translation_key="phase_2_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda report: report.b_apparent_power,
    ),
    ZendureP1SensorEntityDescription(
        key="phase_3_apparent_power",
        translation_key="phase_3_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda report: report.c_apparent_power,
    ),
    ZendureP1SensorEntityDescription(
        key="total_power",
        translation_key="total_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda report: report.total_power,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZendureP1ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zendure Smart Meter P1 sensor entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        ZendureP1SensorEntity(coordinator, description) for description in SENSORS
    )


class ZendureP1SensorEntity(ZendureP1Entity, SensorEntity):
    """Defines a Zendure Smart Meter P1 sensor entity."""

    entity_description: ZendureP1SensorEntityDescription

    def __init__(
        self,
        coordinator: ZendureP1Coordinator,
        description: ZendureP1SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.device_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

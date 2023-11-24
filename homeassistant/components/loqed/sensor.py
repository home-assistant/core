"""Creates LOQED sensors."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from loqedAPI import loqed

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import BATTERY_TYPES, DOMAIN, EVENT_TYPES
from .coordinator import LoqedDataCoordinator
from .entity import LoqedEntity


@dataclass(kw_only=True)
class LoqedSensorEntityDescription(SensorEntityDescription):
    """Dataclass describing LOQED sensor entities."""

    value_fn: Callable[[loqed.Lock], StateType]


SENSORS: Final[tuple[LoqedSensorEntityDescription, ...]] = (
    LoqedSensorEntityDescription(
        key="last_event",
        value_fn=lambda lock: lock.last_event if lock.last_event else None,
        translation_key="last_event",
        options=EVENT_TYPES,
        icon="mdi:information-outline",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    LoqedSensorEntityDescription(
        key="ble_strength",
        value_fn=lambda lock: lock.ble_strength,
        translation_key="ble_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    LoqedSensorEntityDescription(
        key="wifi_strength",
        value_fn=lambda lock: lock.wifi_strength,
        translation_key="wifi_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    LoqedSensorEntityDescription(
        key="battery_percentage",
        value_fn=lambda lock: lock.battery_percentage,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    LoqedSensorEntityDescription(
        key="battery_voltage",
        value_fn=lambda lock: lock.battery_voltage,
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
    ),
    LoqedSensorEntityDescription(
        key="battery_type",
        value_fn=lambda lock: lock.battery_type.lower(),
        translation_key="battery_type",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:information-outline",
        options=BATTERY_TYPES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Loqed lock platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(LoqedSensor(coordinator, sensor) for sensor in SENSORS)


class LoqedSensor(LoqedEntity, SensorEntity):
    """Representation of Sensor state."""

    entity_description: LoqedSensorEntityDescription

    def __init__(
        self,
        coordinator: LoqedDataCoordinator,
        description: LoqedSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.coordinator.lock.id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return state of sensor."""
        return self.entity_description.value_fn(self.coordinator.lock)

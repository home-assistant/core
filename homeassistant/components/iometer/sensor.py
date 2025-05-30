"""IOmeter sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import IOMeterCoordinator, IOmeterData
from .entity import IOmeterEntity


@dataclass(frozen=True, kw_only=True)
class IOmeterEntityDescription(SensorEntityDescription):
    """Describes IOmeter sensor entity."""

    value_fn: Callable[[IOmeterData], str | int | float]


SENSOR_TYPES: list[IOmeterEntityDescription] = [
    IOmeterEntityDescription(
        key="meter_number",
        translation_key="meter_number",
        icon="mdi:meter-electric",
        value_fn=lambda data: data.status.meter.number,
    ),
    IOmeterEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.status.device.bridge.rssi,
    ),
    IOmeterEntityDescription(
        key="core_bridge_rssi",
        translation_key="core_bridge_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.status.device.core.rssi,
    ),
    IOmeterEntityDescription(
        key="power_status",
        translation_key="power_status",
        device_class=SensorDeviceClass.ENUM,
        options=["battery", "wired", "unknown"],
        value_fn=lambda data: data.status.device.core.power_status or STATE_UNKNOWN,
    ),
    IOmeterEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.status.device.core.battery_level,
    ),
    IOmeterEntityDescription(
        key="pin_status",
        translation_key="pin_status",
        device_class=SensorDeviceClass.ENUM,
        options=["entered", "pending", "missing", "unknown"],
        value_fn=lambda data: data.status.device.core.pin_status or STATE_UNKNOWN,
    ),
    IOmeterEntityDescription(
        key="total_consumption",
        translation_key="total_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.reading.get_total_consumption(),
    ),
    IOmeterEntityDescription(
        key="total_production",
        translation_key="total_production",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.reading.get_total_production(),
    ),
    IOmeterEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.reading.get_current_power(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sensors."""
    coordinator: IOMeterCoordinator = config_entry.runtime_data

    async_add_entities(
        IOmeterSensor(
            coordinator=coordinator,
            description=description,
        )
        for description in SENSOR_TYPES
    )


class IOmeterSensor(IOmeterEntity, SensorEntity):
    """Defines a IOmeter sensor."""

    entity_description: IOmeterEntityDescription

    def __init__(
        self,
        coordinator: IOMeterCoordinator,
        description: IOmeterEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.identifier}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

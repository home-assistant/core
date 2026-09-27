"""Envertech EVT800 sensor."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import EnvertechEVT800ConfigEntry
from .coordinator import EnvertechEVT800Coordinator
from .entity import EnvertechEVT800Entity

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="id_1",
        entity_registry_enabled_default=False,
        translation_key="mppt_id_1",
    ),
    SensorEntityDescription(
        key="id_2",
        entity_registry_enabled_default=False,
        translation_key="mppt_id_2",
    ),
    SensorEntityDescription(
        key="input_voltage_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        translation_key="input_voltage_1",
    ),
    SensorEntityDescription(
        key="input_voltage_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        translation_key="input_voltage_2",
    ),
    SensorEntityDescription(
        key="power_1",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=0,
        translation_key="power_1",
    ),
    SensorEntityDescription(
        key="power_2",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=0,
        translation_key="power_2",
    ),
    SensorEntityDescription(
        key="current_1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        suggested_display_precision=2,
        translation_key="current_1",
    ),
    SensorEntityDescription(
        key="current_2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        suggested_display_precision=2,
        translation_key="current_2",
    ),
    SensorEntityDescription(
        key="ac_frequency_1",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        suggested_display_precision=1,
        translation_key="ac_frequency_1",
    ),
    SensorEntityDescription(
        key="ac_frequency_2",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        suggested_display_precision=1,
        translation_key="ac_frequency_2",
    ),
    SensorEntityDescription(
        key="ac_voltage_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=0,
        translation_key="ac_voltage_1",
    ),
    SensorEntityDescription(
        key="ac_voltage_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=0,
        translation_key="ac_voltage_2",
    ),
    SensorEntityDescription(
        key="temperature_1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        translation_key="temperature_1",
    ),
    SensorEntityDescription(
        key="temperature_2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        translation_key="temperature_2",
    ),
    SensorEntityDescription(
        key="total_energy_1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        translation_key="total_energy_1",
    ),
    SensorEntityDescription(
        key="total_energy_2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        translation_key="total_energy_2",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnvertechEVT800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Envertech EVT800 sensors."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        EnvertechEVT800Sensor(coordinator, description) for description in SENSORS
    )


class EnvertechEVT800Sensor(EnvertechEVT800Entity, SensorEntity):
    """Representation of an Envertech EVT800 sensor."""

    def __init__(
        self,
        coordinator: EnvertechEVT800Coordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.coordinator.client.data.get(self.entity_description.key)

    @property
    @override
    def available(self) -> bool:
        """Unavailable if evt800 isn't connected."""
        return super().available and self.native_value is not None

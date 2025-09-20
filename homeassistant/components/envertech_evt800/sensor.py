"""Envertech EVT800 sensor."""

from typing import Any

import pyenvertechevt800

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EnvertechEVT800ConfigEntry
from .coordinator import EnvertechEVT800Coordinator
from .entity import EnvertechEVT800Entity

SENSORS: dict[str, SensorEntityDescription] = {
    "timestamp": SensorEntityDescription(
        key="timestamp",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        entity_registry_visible_default=False,
        translation_key="timestamp",
    ),
    "id_1": SensorEntityDescription(
        key="id_1",
        entity_registry_enabled_default=False,
        entity_registry_visible_default=True,
        translation_key="mppt_id_1",
    ),
    "id_2": SensorEntityDescription(
        key="id_2",
        entity_registry_enabled_default=False,
        entity_registry_visible_default=True,
        translation_key="mppt_id_2",
    ),
    "input_voltage_1": SensorEntityDescription(
        key="input_voltage_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        translation_key="input_voltage_1",
    ),
    "input_voltage_2": SensorEntityDescription(
        key="input_voltage_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        translation_key="input_voltage_2",
    ),
    "power_1": SensorEntityDescription(
        key="power_1",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=0,
        translation_key="power_1",
    ),
    "power_2": SensorEntityDescription(
        key="power_2",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=0,
        translation_key="power_2",
    ),
    "current_1": SensorEntityDescription(
        key="current_1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        suggested_display_precision=2,
        translation_key="current_1",
    ),
    "current_2": SensorEntityDescription(
        key="current_2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        suggested_display_precision=2,
        translation_key="current_2",
    ),
    "ac_frequency_1": SensorEntityDescription(
        key="ac_frequency_1",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        suggested_display_precision=1,
        translation_key="ac_frequency_1",
    ),
    "ac_frequency_2": SensorEntityDescription(
        key="ac_frequency_2",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
        suggested_display_precision=1,
        translation_key="ac_frequency_2",
    ),
    "ac_voltage_1": SensorEntityDescription(
        key="ac_voltage_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=0,
        translation_key="ac_voltage_1",
    ),
    "ac_voltage_2": SensorEntityDescription(
        key="ac_voltage_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=0,
        translation_key="ac_voltage_2",
    ),
    "temperature_1": SensorEntityDescription(
        key="temperature_1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        translation_key="temperature_1",
    ),
    "temperature_2": SensorEntityDescription(
        key="temperature_2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        translation_key="temperature_2",
    ),
    "total_energy_1": SensorEntityDescription(
        key="total_energy_1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        translation_key="total_energy_1",
    ),
    "total_energy_2": SensorEntityDescription(
        key="total_energy_2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        translation_key="total_energy_2",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnvertechEVT800ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Envertech EVT800 sensors."""

    evt800: pyenvertechevt800.EnvertechEVT800 = config_entry.runtime_data.client
    coordinator: EnvertechEVT800Coordinator = config_entry.runtime_data

    entities = []
    for name, description in SENSORS.items():
        data = evt800.data.get(name)
        entities.append(
            EnvertechEVT800Sensor(
                evt800,
                coordinator,
                config_entry,
                description,
                name,
                data,
            )
        )
    if entities:
        async_add_entities(entities)


class EnvertechEVT800Sensor(EnvertechEVT800Entity, SensorEntity):
    """Representation of a Envertech EVT800 sensor."""

    def __init__(
        self,
        evt800: pyenvertechevt800.EnvertechEVT800,
        coordinator: EnvertechEVT800Coordinator,
        config_entry: ConfigEntry[Any],
        description: SensorEntityDescription | None,
        name: str,
        value: Any,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(evt800, coordinator, config_entry)
        if description is not None:
            self.entity_description = description
        else:
            self._attr_name = name

        self._value = value
        self._device = evt800
        self._key = name

        self._attr_has_entity_name = True
        self._attr_unique_id = f"{config_entry.unique_id}-{name}"
        self._attr_native_value = self._device.data[self._key]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Return the state of the sensor."""
        self._attr_native_value = self._device.data[self._key]
        self.async_write_ha_state()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Unavailable if evt800 isn't connected."""
        return (
            self._device.online
            and self._device.data[self._key] is not None
            and super().available
        )

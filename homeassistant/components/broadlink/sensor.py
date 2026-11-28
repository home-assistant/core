"""Support for Broadlink sensors."""

from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfDensity,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BROADLINK_DATA
from .entity import BroadlinkEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="air_quality",
        device_class=SensorDeviceClass.AQI,
    ),
    SensorEntityDescription(
        key="pm10",
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm2_5",
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm1",
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="light",
        translation_key="light",
    ),
    SensorEntityDescription(
        key="noise",
        translation_key="noise",
    ),
    SensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="volt",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="overload",
        translation_key="overload",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="totalconsum",
        translation_key="total_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="tvoc",
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="formaldehyde",
        translation_key="formaldehyde",
        native_unit_of_measurement=UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Broadlink sensor."""
    device = hass.data[BROADLINK_DATA].devices[config_entry.entry_id]
    if TYPE_CHECKING:
        assert device.update_manager is not None
    sensor_data = device.update_manager.coordinator.data
    if TYPE_CHECKING:
        assert sensor_data is not None
    sensors = [
        BroadlinkSensor(device, description)
        for description in SENSOR_TYPES
        if description.key in sensor_data
        and (
            # These devices have optional sensors.
            # We don't create entities if the value is 0.
            sensor_data[description.key] != 0
            or device.api.type not in {"RM4PRO", "RM4MINI"}
        )
    ]
    async_add_entities(sensors)


class BroadlinkSensor(BroadlinkEntity, SensorEntity):
    """Representation of a Broadlink sensor."""

    _attr_has_entity_name = True

    def __init__(self, device, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self.entity_description = description

        self._attr_native_value = self._coordinator.data[description.key]
        self._attr_unique_id = f"{device.unique_id}-{description.key}"

    @override
    def _update_state(self, data):
        """Update the state of the entity."""
        # These sensors belong to a purifier unit that can be offline independently.
        if self._device.api.type == "LIFAAIR" and self.entity_description.key in {
            "temperature",
            "humidity",
        }:
            self._attr_available = data["purifier_online"]
        self._attr_native_value = data[self.entity_description.key]

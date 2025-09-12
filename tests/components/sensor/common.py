"""Common test utilities for sensor entity component tests."""

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.components.sensor.const import DEVICE_CLASS_STATE_CLASSES
from homeassistant.const import (
    CONCENTRATION_GRAMS_PER_CUBIC_METER,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfApparentPower,
    UnitOfArea,
    UnitOfBloodGlucoseConcentration,
    UnitOfConductivity,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfEnergyDistance,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfVolumetricFlux,
)

from tests.common import MockEntity

UNITS_OF_MEASUREMENT = {
    SensorDeviceClass.ABSOLUTE_HUMIDITY: CONCENTRATION_GRAMS_PER_CUBIC_METER,
    SensorDeviceClass.APPARENT_POWER: UnitOfApparentPower.VOLT_AMPERE,
    SensorDeviceClass.AQI: None,
    SensorDeviceClass.AREA: UnitOfArea.SQUARE_METERS,
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: UnitOfPressure.HPA,
    SensorDeviceClass.BATTERY: PERCENTAGE,
    SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION: UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER,
    SensorDeviceClass.CO2: CONCENTRATION_PARTS_PER_MILLION,
    SensorDeviceClass.CO: CONCENTRATION_PARTS_PER_MILLION,
    SensorDeviceClass.CONDUCTIVITY: UnitOfConductivity.SIEMENS_PER_CM,
    SensorDeviceClass.CURRENT: UnitOfElectricCurrent.AMPERE,
    SensorDeviceClass.DATA_RATE: UnitOfDataRate.BITS_PER_SECOND,
    SensorDeviceClass.DATA_SIZE: UnitOfInformation.BYTES,
    SensorDeviceClass.DATE: None,
    SensorDeviceClass.DISTANCE: UnitOfLength.METERS,
    SensorDeviceClass.DURATION: UnitOfTime.SECONDS,
    SensorDeviceClass.ENERGY: UnitOfEnergy.KILO_WATT_HOUR,
    SensorDeviceClass.ENERGY_DISTANCE: UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
    SensorDeviceClass.ENERGY_STORAGE: UnitOfEnergy.KILO_WATT_HOUR,
    SensorDeviceClass.ENUM: None,
    SensorDeviceClass.FREQUENCY: UnitOfFrequency.GIGAHERTZ,
    SensorDeviceClass.GAS: UnitOfVolume.CUBIC_METERS,
    SensorDeviceClass.HUMIDITY: PERCENTAGE,
    SensorDeviceClass.ILLUMINANCE: LIGHT_LUX,
    SensorDeviceClass.IRRADIANCE: UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    SensorDeviceClass.MOISTURE: PERCENTAGE,
    SensorDeviceClass.MONETARY: None,
    SensorDeviceClass.NITROGEN_DIOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.NITROGEN_MONOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.NITROUS_OXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.OZONE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.PH: None,
    SensorDeviceClass.PM10: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.PM1: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.PM25: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.POWER: UnitOfPower.KILO_WATT,
    SensorDeviceClass.POWER_FACTOR: PERCENTAGE,
    SensorDeviceClass.PRECIPITATION: UnitOfPrecipitationDepth.MILLIMETERS,
    SensorDeviceClass.PRECIPITATION_INTENSITY: UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    SensorDeviceClass.PRESSURE: UnitOfPressure.HPA,
    SensorDeviceClass.REACTIVE_ENERGY: UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
    SensorDeviceClass.REACTIVE_POWER: UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    SensorDeviceClass.SIGNAL_STRENGTH: SIGNAL_STRENGTH_DECIBELS,
    SensorDeviceClass.SOUND_PRESSURE: UnitOfSoundPressure.DECIBEL,
    SensorDeviceClass.SPEED: UnitOfSpeed.METERS_PER_SECOND,
    SensorDeviceClass.SULPHUR_DIOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.TEMPERATURE: UnitOfTemperature.CELSIUS,
    SensorDeviceClass.TIMESTAMP: None,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS: CONCENTRATION_PARTS_PER_MILLION,
    SensorDeviceClass.VOLTAGE: UnitOfElectricPotential.VOLT,
    SensorDeviceClass.VOLUME: UnitOfVolume.LITERS,
    SensorDeviceClass.VOLUME_FLOW_RATE: UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    SensorDeviceClass.VOLUME_STORAGE: UnitOfVolume.LITERS,
    SensorDeviceClass.WATER: UnitOfVolume.LITERS,
    SensorDeviceClass.WEIGHT: UnitOfMass.KILOGRAMS,
    SensorDeviceClass.WIND_DIRECTION: DEGREE,
    SensorDeviceClass.WIND_SPEED: UnitOfSpeed.METERS_PER_SECOND,
}
assert UNITS_OF_MEASUREMENT.keys() == {cls.value for cls in SensorDeviceClass}


class MockSensor(MockEntity, SensorEntity):
    """Mock Sensor class."""

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._handle("device_class")

    @property
    def last_reset(self):
        """Return the last_reset of this sensor."""
        return self._handle("last_reset")

    @property
    def suggested_display_precision(self):
        """Return the number of digits after the decimal point."""
        return self._handle("suggested_display_precision")

    @property
    def native_unit_of_measurement(self):
        """Return the native unit_of_measurement of this sensor."""
        return self._handle("native_unit_of_measurement")

    @property
    def native_value(self):
        """Return the native value of this sensor."""
        return self._handle("native_value")

    @property
    def options(self):
        """Return the options for this sensor."""
        return self._handle("options")

    @property
    def state_class(self):
        """Return the state class of this sensor."""
        return self._handle("state_class")

    @property
    def suggested_unit_of_measurement(self):
        """Return the state class of this sensor."""
        return self._handle("suggested_unit_of_measurement")


class MockRestoreSensor(MockSensor, RestoreSensor):
    """Mock RestoreSensor class."""

    async def async_added_to_hass(self) -> None:
        """Restore native_value and native_unit_of_measurement."""
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_sensor_data()) is None:
            return
        self._values["native_value"] = last_sensor_data.native_value
        self._values["native_unit_of_measurement"] = (
            last_sensor_data.native_unit_of_measurement
        )


def get_mock_sensor_entities() -> dict[str, MockSensor]:
    """Get mock sensor entities."""
    return {
        device_class: MockSensor(
            name=f"{device_class} sensor",
            unique_id=f"unique_{device_class}",
            device_class=device_class,
            state_class=DEVICE_CLASS_STATE_CLASSES.get(device_class),
            native_unit_of_measurement=UNITS_OF_MEASUREMENT.get(device_class),
        )
        for device_class in SensorDeviceClass
    }

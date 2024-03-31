"""Common test utilities for sensor entity component tests."""

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_VOLT_AMPERE_REACTIVE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfApparentPower,
    UnitOfFrequency,
    UnitOfPressure,
    UnitOfVolume,
)

from tests.common import MockEntity

UNITS_OF_MEASUREMENT = {
    SensorDeviceClass.APPARENT_POWER: UnitOfApparentPower.VOLT_AMPERE,  # apparent power (VA)
    SensorDeviceClass.BATTERY: PERCENTAGE,  # % of battery that is left
    SensorDeviceClass.CO: CONCENTRATION_PARTS_PER_MILLION,  # ppm of CO concentration
    SensorDeviceClass.CO2: CONCENTRATION_PARTS_PER_MILLION,  # ppm of CO2 concentration
    SensorDeviceClass.HUMIDITY: PERCENTAGE,  # % of humidity in the air
    SensorDeviceClass.ILLUMINANCE: LIGHT_LUX,  # current light level lx
    SensorDeviceClass.MOISTURE: PERCENTAGE,  # % of water in a substance
    SensorDeviceClass.NITROGEN_DIOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of nitrogen dioxide
    SensorDeviceClass.NITROGEN_MONOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of nitrogen monoxide
    SensorDeviceClass.NITROUS_OXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of nitrogen oxide
    SensorDeviceClass.OZONE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of ozone
    SensorDeviceClass.PM1: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of PM1
    SensorDeviceClass.PM10: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of PM10
    SensorDeviceClass.PM25: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of PM2.5
    SensorDeviceClass.SIGNAL_STRENGTH: SIGNAL_STRENGTH_DECIBELS,  # signal strength (dB/dBm)
    SensorDeviceClass.SULPHUR_DIOXIDE: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of sulphur dioxide
    SensorDeviceClass.TEMPERATURE: "C",  # temperature (C/F)
    SensorDeviceClass.PRESSURE: UnitOfPressure.HPA,  # pressure (hPa/mbar)
    SensorDeviceClass.POWER: "kW",  # power (W/kW)
    SensorDeviceClass.CURRENT: "A",  # current (A)
    SensorDeviceClass.ENERGY: "kWh",  # energy (Wh/kWh/MWh)
    SensorDeviceClass.FREQUENCY: UnitOfFrequency.GIGAHERTZ,  # energy (Hz/kHz/MHz/GHz)
    SensorDeviceClass.POWER_FACTOR: PERCENTAGE,  # power factor (no unit, min: -1.0, max: 1.0)
    SensorDeviceClass.REACTIVE_POWER: POWER_VOLT_AMPERE_REACTIVE,  # reactive power (var)
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,  # µg/m³ of vocs
    SensorDeviceClass.VOLTAGE: "V",  # voltage (V)
    SensorDeviceClass.GAS: UnitOfVolume.CUBIC_METERS,  # gas (m³)
}


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
            native_unit_of_measurement=UNITS_OF_MEASUREMENT.get(device_class),
        )
        for device_class in SensorDeviceClass
    }

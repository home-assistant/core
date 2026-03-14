"""Tests for the BACnet unit mapping."""

from __future__ import annotations

from homeassistant.components.bacnet.units import get_unit_mapping
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)


def test_temperature_units() -> None:
    """Test temperature unit mappings."""
    mapping = get_unit_mapping("degreesCelsius")
    assert mapping.ha_unit == UnitOfTemperature.CELSIUS
    assert mapping.device_class == SensorDeviceClass.TEMPERATURE
    assert mapping.state_class == SensorStateClass.MEASUREMENT

    mapping = get_unit_mapping("degreesFahrenheit")
    assert mapping.ha_unit == UnitOfTemperature.FAHRENHEIT
    assert mapping.device_class == SensorDeviceClass.TEMPERATURE

    mapping = get_unit_mapping("degreesKelvin")
    assert mapping.ha_unit == UnitOfTemperature.KELVIN
    assert mapping.device_class == SensorDeviceClass.TEMPERATURE


def test_power_units() -> None:
    """Test power unit mappings."""
    mapping = get_unit_mapping("watts")
    assert mapping.ha_unit == UnitOfPower.WATT
    assert mapping.device_class == SensorDeviceClass.POWER

    mapping = get_unit_mapping("kilowatts")
    assert mapping.ha_unit == UnitOfPower.KILO_WATT
    assert mapping.device_class == SensorDeviceClass.POWER


def test_energy_units() -> None:
    """Test energy unit mappings."""
    mapping = get_unit_mapping("kilowattHours")
    assert mapping.ha_unit == UnitOfEnergy.KILO_WATT_HOUR
    assert mapping.device_class == SensorDeviceClass.ENERGY
    assert mapping.state_class == SensorStateClass.TOTAL_INCREASING

    mapping = get_unit_mapping("joules")
    assert mapping.ha_unit == UnitOfEnergy.JOULE
    assert mapping.device_class == SensorDeviceClass.ENERGY


def test_electrical_units() -> None:
    """Test electrical unit mappings."""
    mapping = get_unit_mapping("amperes")
    assert mapping.ha_unit == UnitOfElectricCurrent.AMPERE
    assert mapping.device_class == SensorDeviceClass.CURRENT

    mapping = get_unit_mapping("volts")
    assert mapping.ha_unit == UnitOfElectricPotential.VOLT
    assert mapping.device_class == SensorDeviceClass.VOLTAGE


def test_pressure_units() -> None:
    """Test pressure unit mappings."""
    mapping = get_unit_mapping("pascals")
    assert mapping.ha_unit == UnitOfPressure.PA
    assert mapping.device_class == SensorDeviceClass.PRESSURE

    mapping = get_unit_mapping("bars")
    assert mapping.ha_unit == UnitOfPressure.BAR


def test_humidity_units() -> None:
    """Test humidity unit mappings."""
    mapping = get_unit_mapping("percentRelativeHumidity")
    assert mapping.ha_unit == PERCENTAGE
    assert mapping.device_class == SensorDeviceClass.HUMIDITY


def test_frequency_units() -> None:
    """Test frequency unit mappings."""
    mapping = get_unit_mapping("hertz")
    assert mapping.ha_unit == UnitOfFrequency.HERTZ
    assert mapping.device_class == SensorDeviceClass.FREQUENCY


def test_distance_units() -> None:
    """Test distance unit mappings."""
    mapping = get_unit_mapping("meters")
    assert mapping.ha_unit == UnitOfLength.METERS
    assert mapping.device_class == SensorDeviceClass.DISTANCE


def test_volume_units() -> None:
    """Test volume unit mappings."""
    mapping = get_unit_mapping("liters")
    assert mapping.ha_unit == UnitOfVolume.LITERS
    assert mapping.device_class == SensorDeviceClass.VOLUME


def test_unknown_unit() -> None:
    """Test that unknown units return default mapping."""
    mapping = get_unit_mapping("unknownUnit")
    assert mapping.ha_unit is None
    assert mapping.device_class is None
    assert mapping.state_class == SensorStateClass.MEASUREMENT


def test_no_units() -> None:
    """Test noUnits mapping."""
    mapping = get_unit_mapping("noUnits")
    assert mapping.ha_unit is None
    assert mapping.device_class is None


def test_percent_units() -> None:
    """Test percent mapping."""
    mapping = get_unit_mapping("percent")
    assert mapping.ha_unit == PERCENTAGE
    assert mapping.device_class is None


def test_btu_power_units() -> None:
    """Test BTU/hour power unit mapping."""
    mapping = get_unit_mapping("btusPerHour")
    assert mapping.ha_unit == UnitOfPower.BTU_PER_HOUR
    assert mapping.device_class == SensorDeviceClass.POWER


def test_hectopascals_pressure() -> None:
    """Test hectopascals pressure unit mapping."""
    mapping = get_unit_mapping("hectopascals")
    assert mapping.ha_unit == UnitOfPressure.HPA
    assert mapping.device_class == SensorDeviceClass.PRESSURE


def test_volume_flow_rate_units() -> None:
    """Test volume flow rate unit mappings."""
    mapping = get_unit_mapping("litersPerSecond")
    assert mapping.ha_unit == UnitOfVolumeFlowRate.LITERS_PER_SECOND
    assert mapping.device_class == SensorDeviceClass.VOLUME_FLOW_RATE

    mapping = get_unit_mapping("cubicMetersPerMinute")
    assert mapping.ha_unit == UnitOfVolumeFlowRate.CUBIC_METERS_PER_MINUTE
    assert mapping.device_class == SensorDeviceClass.VOLUME_FLOW_RATE


def test_irradiance_units() -> None:
    """Test irradiance unit mappings."""
    mapping = get_unit_mapping("wattsPerSquareMeter")
    assert mapping.ha_unit == UnitOfIrradiance.WATTS_PER_SQUARE_METER
    assert mapping.device_class == SensorDeviceClass.IRRADIANCE

    mapping = get_unit_mapping("wattsPerSquareFoot")
    assert mapping.ha_unit == UnitOfIrradiance.WATTS_PER_SQUARE_METER
    assert mapping.device_class == SensorDeviceClass.IRRADIANCE


def test_air_quality_concentration_units() -> None:
    """Test air quality concentration unit mappings."""
    # PM2.5
    mapping = get_unit_mapping("microgramsPerCubicMeter")
    assert mapping.ha_unit == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    assert mapping.device_class == SensorDeviceClass.PM25

    # PM10
    mapping = get_unit_mapping("milligramsPerCubicMeter")
    assert mapping.ha_unit == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    assert mapping.device_class == SensorDeviceClass.PM10

    # CO2
    mapping = get_unit_mapping("partsPerMillion")
    assert mapping.ha_unit == CONCENTRATION_PARTS_PER_MILLION
    assert mapping.device_class == SensorDeviceClass.CO2

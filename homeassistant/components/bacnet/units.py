"""BACnet engineering units to Home Assistant unit mapping."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfApparentPower,
    UnitOfArea,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactivePower,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)


@dataclass(frozen=True)
class BACnetUnitMapping:
    """Map a BACnet engineering unit to Home Assistant units."""

    ha_unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT


# Mapping from BACnet EngineeringUnits string names to HA units/device classes
# Keys correspond to the .attr property values of EngineeringUnits enum members from BACpypes3
# Using string literals here allows module load without importing bacpypes3,
# while bacnet_client.py validates these at runtime using EngineeringUnits enum
BACNET_UNIT_MAP: dict[str, BACnetUnitMapping] = {
    # Temperature
    "degreesCelsius": BACnetUnitMapping(
        ha_unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "degreesFahrenheit": BACnetUnitMapping(
        ha_unit=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "degreesKelvin": BACnetUnitMapping(
        ha_unit=UnitOfTemperature.KELVIN,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    # Power
    "watts": BACnetUnitMapping(
        ha_unit=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    "kilowatts": BACnetUnitMapping(
        ha_unit=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    "megawatts": BACnetUnitMapping(
        ha_unit=UnitOfPower.MEGA_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    "horsepower": BACnetUnitMapping(
        ha_unit=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    "btusPerHour": BACnetUnitMapping(
        ha_unit=UnitOfPower.BTU_PER_HOUR,
        device_class=SensorDeviceClass.POWER,
    ),
    # Energy
    "wattHours": BACnetUnitMapping(
        ha_unit=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "kilowattHours": BACnetUnitMapping(
        ha_unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "megawattHours": BACnetUnitMapping(
        ha_unit=UnitOfEnergy.MEGA_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "joules": BACnetUnitMapping(
        ha_unit=UnitOfEnergy.JOULE,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "kilojoules": BACnetUnitMapping(
        ha_unit=UnitOfEnergy.KILO_JOULE,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "megajoules": BACnetUnitMapping(
        ha_unit=UnitOfEnergy.MEGA_JOULE,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    # Apparent power
    "voltAmperes": BACnetUnitMapping(
        ha_unit=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
    ),
    "kilovoltAmperes": BACnetUnitMapping(
        ha_unit=UnitOfApparentPower.KILO_VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
    ),
    # Reactive power
    "voltAmperesReactive": BACnetUnitMapping(
        ha_unit=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    "kilovoltAmperesReactive": BACnetUnitMapping(
        ha_unit=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    # Electrical - current
    "amperes": BACnetUnitMapping(
        ha_unit=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
    ),
    "milliamperes": BACnetUnitMapping(
        ha_unit=UnitOfElectricCurrent.MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
    ),
    # Electrical - voltage
    "volts": BACnetUnitMapping(
        ha_unit=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "millivolts": BACnetUnitMapping(
        ha_unit=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "kilovolts": BACnetUnitMapping(
        ha_unit=UnitOfElectricPotential.KILOVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "megavolts": BACnetUnitMapping(
        ha_unit=UnitOfElectricPotential.MEGAVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # Power factor
    "powerFactor": BACnetUnitMapping(
        ha_unit=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
    ),
    # Pressure
    "pascals": BACnetUnitMapping(
        ha_unit=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    "hectopascals": BACnetUnitMapping(
        ha_unit=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    "kilopascals": BACnetUnitMapping(
        ha_unit=UnitOfPressure.KPA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    "bars": BACnetUnitMapping(
        ha_unit=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    "poundsForcePerSquareInch": BACnetUnitMapping(
        ha_unit=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    "millimetersOfMercury": BACnetUnitMapping(
        ha_unit=UnitOfPressure.MMHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    "inchesOfMercury": BACnetUnitMapping(
        ha_unit=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    "inchesOfWater": BACnetUnitMapping(
        ha_unit=UnitOfPressure.INH2O,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    # Humidity
    "percentRelativeHumidity": BACnetUnitMapping(
        ha_unit=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    # Percentage
    "percent": BACnetUnitMapping(
        ha_unit=PERCENTAGE,
    ),
    # Frequency
    "hertz": BACnetUnitMapping(
        ha_unit=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    "kilohertz": BACnetUnitMapping(
        ha_unit=UnitOfFrequency.KILOHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    "megahertz": BACnetUnitMapping(
        ha_unit=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    "revolutionsPerMinute": BACnetUnitMapping(
        ha_unit=REVOLUTIONS_PER_MINUTE,
    ),
    # Time
    "seconds": BACnetUnitMapping(
        ha_unit=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    "milliseconds": BACnetUnitMapping(
        ha_unit=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    "minutes": BACnetUnitMapping(
        ha_unit=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
    ),
    "hours": BACnetUnitMapping(
        ha_unit=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
    ),
    "days": BACnetUnitMapping(
        ha_unit=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
    ),
    # Distance
    "meters": BACnetUnitMapping(
        ha_unit=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    "centimeters": BACnetUnitMapping(
        ha_unit=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    "millimeters": BACnetUnitMapping(
        ha_unit=UnitOfLength.MILLIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    "kilometers": BACnetUnitMapping(
        ha_unit=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    "feet": BACnetUnitMapping(
        ha_unit=UnitOfLength.FEET,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    "inches": BACnetUnitMapping(
        ha_unit=UnitOfLength.INCHES,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    # Area
    "squareMeters": BACnetUnitMapping(
        ha_unit=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
    ),
    "squareFeet": BACnetUnitMapping(
        ha_unit=UnitOfArea.SQUARE_FEET,
        device_class=SensorDeviceClass.AREA,
    ),
    "squareCentimeters": BACnetUnitMapping(
        ha_unit=UnitOfArea.SQUARE_CENTIMETERS,
        device_class=SensorDeviceClass.AREA,
    ),
    "squareInches": BACnetUnitMapping(
        ha_unit=UnitOfArea.SQUARE_INCHES,
        device_class=SensorDeviceClass.AREA,
    ),
    # Volume (state_class=None because volume only supports total/total_increasing,
    # and BACnet volume objects may be tank levels or flow totals)
    "cubicFeet": BACnetUnitMapping(
        ha_unit=UnitOfVolume.CUBIC_FEET,
        device_class=SensorDeviceClass.VOLUME,
        state_class=None,
    ),
    "cubicMeters": BACnetUnitMapping(
        ha_unit=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=None,
    ),
    "liters": BACnetUnitMapping(
        ha_unit=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=None,
    ),
    "usGallons": BACnetUnitMapping(
        ha_unit=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=None,
    ),
    # Volume flow rate
    "cubicFeetPerMinute": BACnetUnitMapping(
        ha_unit=UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    "cubicMetersPerSecond": BACnetUnitMapping(
        ha_unit=UnitOfVolumeFlowRate.CUBIC_METERS_PER_SECOND,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    "cubicMetersPerMinute": BACnetUnitMapping(
        ha_unit=UnitOfVolumeFlowRate.CUBIC_METERS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    "cubicMetersPerHour": BACnetUnitMapping(
        ha_unit=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    "litersPerMinute": BACnetUnitMapping(
        ha_unit=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    "litersPerSecond": BACnetUnitMapping(
        ha_unit=UnitOfVolumeFlowRate.LITERS_PER_SECOND,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    "litersPerHour": BACnetUnitMapping(
        ha_unit=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    "usGallonsPerMinute": BACnetUnitMapping(
        ha_unit=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    # Mass
    "kilograms": BACnetUnitMapping(
        ha_unit=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
    ),
    "grams": BACnetUnitMapping(
        ha_unit=UnitOfMass.GRAMS,
        device_class=SensorDeviceClass.WEIGHT,
    ),
    "milligrams": BACnetUnitMapping(
        ha_unit=UnitOfMass.MILLIGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
    ),
    "poundsMass": BACnetUnitMapping(
        ha_unit=UnitOfMass.POUNDS,
        device_class=SensorDeviceClass.WEIGHT,
    ),
    # Speed
    "metersPerSecond": BACnetUnitMapping(
        ha_unit=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
    ),
    "kilometersPerHour": BACnetUnitMapping(
        ha_unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
    ),
    "milesPerHour": BACnetUnitMapping(
        ha_unit=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
    ),
    "feetPerMinute": BACnetUnitMapping(
        ha_unit=UnitOfSpeed.FEET_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
    ),
    # Illuminance
    "luxes": BACnetUnitMapping(
        ha_unit=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
    ),
    # Irradiance
    "wattsPerSquareMeter": BACnetUnitMapping(
        ha_unit=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
    ),
    "wattsPerSquareFoot": BACnetUnitMapping(
        ha_unit=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
    ),
    # Concentration
    "partsPerMillion": BACnetUnitMapping(
        ha_unit=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
    ),
    "partsPerBillion": BACnetUnitMapping(
        ha_unit=CONCENTRATION_PARTS_PER_BILLION,
    ),
    "microgramsPerCubicMeter": BACnetUnitMapping(
        ha_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
    ),
    "milligramsPerCubicMeter": BACnetUnitMapping(
        ha_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
    ),
    # Sound
    "decibels": BACnetUnitMapping(
        ha_unit=UnitOfSoundPressure.DECIBEL,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
    ),
    "decibelsA": BACnetUnitMapping(
        ha_unit=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
    ),
    # pH
    "pH": BACnetUnitMapping(
        device_class=SensorDeviceClass.PH,
    ),
    # No units
    "noUnits": BACnetUnitMapping(),
}


def get_unit_mapping(bacnet_units: str) -> BACnetUnitMapping:
    """Get the Home Assistant unit mapping for a BACnet engineering unit."""
    return BACNET_UNIT_MAP.get(bacnet_units, BACnetUnitMapping())

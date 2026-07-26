"""Constants for the Ridder HortiMaX Pro (HortOS) integration."""

import logging
from typing import Final

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfConductivity,
    UnitOfEnergy,
    UnitOfIrradiance,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

DOMAIN: Final = "hortimax"
LOGGER: Final = logging.getLogger(__package__)
MANUFACTURER: Final = "Ridder"

CONF_BASE_URL: Final = "base_url"

#: Unchanged readouts are refreshed at most every five minutes, and each poll
#: costs one request per controller against a limit of 100 per 15 seconds.
SCAN_INTERVAL: Final = 60  # seconds

# Dimensionless readouts are mostly status/override codes, so they get neither
# a unit nor statistics.
DIMENSIONLESS_UNITS: Final = {"Scalar", "None"}

# Seconds since local midnight (SunriseToday = 19145 -> 05:19), rendered as a
# timestamp. Keyed by lowercased identifier subject, see naming.py.
TIME_OF_DAY_READOUTS: Final[frozenset[str]] = frozenset({"sunrisetoday", "sunsettoday"})

# Icons for readouts that have no device class, and so no automatic icon.
READOUT_ICONS: Final[dict[str, str]] = {
    # A g/kg mixing ratio, not a relative humidity.
    "absolutehumidity": "mdi:water-opacity",
    "radiationsum": "mdi:sun-wireless",
    # A g/kg moisture shortfall, not a pressure, so VPD does not apply.
    "humiditydeficit": "mdi:water-minus",
}

# An enumeration member id rather than a bearing; aiohortos owns the table.
# This only decides which readout gets the wind direction device class.
WIND_DIRECTION_SUBJECT: Final = "cardinalwinddirection"

# HortOS unit identifiers to Home Assistant units. Unknown identifiers fall
# back to the raw string, without a device class.
UNIT_MAP: Final[dict[str, str]] = {
    # Observed on a live installation
    "Percent": PERCENTAGE,
    "DegreeCelsius": UnitOfTemperature.CELSIUS,
    "Second": UnitOfTime.SECONDS,
    "Minute": UnitOfTime.MINUTES,
    "Gram/Kilogram": "g/kg",
    "Joule/SquareCentimeter": "J/cm²",
    "Liter/Minute": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    "Liter/SquareMeter": "l/m²",
    "KilowattHour": UnitOfEnergy.KILO_WATT_HOUR,
    "Watt/SquareMeter": UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    "Meter/Second": UnitOfSpeed.METERS_PER_SECOND,
    "CubicMeter": UnitOfVolume.CUBIC_METERS,
    # Plausible variants, not yet observed
    "DegreesCelsius": UnitOfTemperature.CELSIUS,
    "DegreeFahrenheit": UnitOfTemperature.FAHRENHEIT,
    "DegreesFahrenheit": UnitOfTemperature.FAHRENHEIT,
    "Kelvin": UnitOfTemperature.KELVIN,
    "Percentage": PERCENTAGE,
    "PartsPerMillion": UnitOfRatio.PARTS_PER_MILLION,
    "Joule/SquareMeter": "J/m²",
    "Kilometer/Hour": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "Degrees": DEGREE,
    "Degree": DEGREE,
    "Liter": UnitOfVolume.LITERS,
    "Milliliter": UnitOfVolume.MILLILITERS,
    "Milliliter/SquareMeter": "ml/m²",
    "CubicMeter/Hour": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "Kilogram": UnitOfMass.KILOGRAMS,
    "Gram": UnitOfMass.GRAMS,
    "Hour": UnitOfTime.HOURS,
    "MilliSiemens/Centimeter": UnitOfConductivity.MILLISIEMENS_PER_CM,
    "MicroSiemens/Centimeter": UnitOfConductivity.MICROSIEMENS_PER_CM,
    "Ph": "pH",
    "PH": "pH",
    "Bar": UnitOfPressure.BAR,
    "MilliBar": UnitOfPressure.MBAR,
    "HectoPascal": UnitOfPressure.HPA,
    "Pascal": UnitOfPressure.PA,
    "Gram/CubicMeter": "g/m³",
    "Micromol/SquareMeter/Second": "µmol/m²/s",
    "Mol/SquareMeter/Day": "mol/m²/d",
    "Lux": LIGHT_LUX,
    "Watt": UnitOfPower.WATT,
    "Kilowatt": UnitOfPower.KILO_WATT,
}

# Display only; recorded states keep full precision. The API emits
# float32-converted doubles (90.15303039550781 %), so a default is needed.
UNIT_PRECISION: Final[dict[str, int]] = {
    UnitOfTemperature.CELSIUS: 1,
    UnitOfTemperature.FAHRENHEIT: 1,
    UnitOfTemperature.KELVIN: 1,
    PERCENTAGE: 1,
    "g/kg": 1,
    "g/m³": 1,
    "J/cm²": 1,
    "J/m²": 0,
    UnitOfSpeed.METERS_PER_SECOND: 1,
    UnitOfSpeed.KILOMETERS_PER_HOUR: 1,
    UnitOfVolumeFlowRate.LITERS_PER_MINUTE: 1,
    UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR: 1,
    "l/m²": 1,
    "ml/m²": 0,
    UnitOfEnergy.KILO_WATT_HOUR: 2,
    UnitOfVolume.CUBIC_METERS: 2,
    UnitOfVolume.LITERS: 1,
    UnitOfVolume.MILLILITERS: 0,
    UnitOfTime.SECONDS: 0,
    UnitOfTime.MINUTES: 0,
    UnitOfTime.HOURS: 1,
    UnitOfIrradiance.WATTS_PER_SQUARE_METER: 0,
    UnitOfRatio.PARTS_PER_MILLION: 0,
    LIGHT_LUX: 0,
    UnitOfConductivity.MILLISIEMENS_PER_CM: 2,
    UnitOfConductivity.MICROSIEMENS_PER_CM: 0,
    "pH": 1,
    UnitOfPressure.BAR: 2,
    UnitOfPressure.MBAR: 0,
    UnitOfPressure.HPA: 0,
    UnitOfPressure.PA: 0,
    "µmol/m²/s": 0,
    "mol/m²/d": 1,
    DEGREE: 0,
    UnitOfPower.WATT: 0,
    UnitOfPower.KILO_WATT: 2,
    UnitOfMass.KILOGRAMS: 1,
    UnitOfMass.GRAMS: 0,
}

# Device classes that follow from the unit alone. Those that also need the
# readout identifier (humidity, wind, gas) are handled in sensor.py.
UNIT_DEVICE_CLASS: Final[dict[str, SensorDeviceClass]] = {
    UnitOfTemperature.CELSIUS: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.FAHRENHEIT: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.KELVIN: SensorDeviceClass.TEMPERATURE,
    UnitOfIrradiance.WATTS_PER_SQUARE_METER: SensorDeviceClass.IRRADIANCE,
    LIGHT_LUX: SensorDeviceClass.ILLUMINANCE,
    UnitOfTime.SECONDS: SensorDeviceClass.DURATION,
    UnitOfTime.MINUTES: SensorDeviceClass.DURATION,
    UnitOfTime.HOURS: SensorDeviceClass.DURATION,
    UnitOfEnergy.KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
    UnitOfPower.WATT: SensorDeviceClass.POWER,
    UnitOfPower.KILO_WATT: SensorDeviceClass.POWER,
    UnitOfConductivity.MILLISIEMENS_PER_CM: SensorDeviceClass.CONDUCTIVITY,
    UnitOfConductivity.MICROSIEMENS_PER_CM: SensorDeviceClass.CONDUCTIVITY,
    UnitOfVolumeFlowRate.LITERS_PER_MINUTE: SensorDeviceClass.VOLUME_FLOW_RATE,
    UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR: SensorDeviceClass.VOLUME_FLOW_RATE,
    UnitOfMass.KILOGRAMS: SensorDeviceClass.WEIGHT,
    UnitOfMass.GRAMS: SensorDeviceClass.WEIGHT,
    UnitOfPressure.BAR: SensorDeviceClass.PRESSURE,
    UnitOfPressure.MBAR: SensorDeviceClass.PRESSURE,
    UnitOfPressure.HPA: SensorDeviceClass.PRESSURE,
    UnitOfPressure.PA: SensorDeviceClass.PRESSURE,
}

# pH has no device class on purpose: SensorDeviceClass.PH accepts no unit, and
# keeping the "pH" unit is worth more than the class.

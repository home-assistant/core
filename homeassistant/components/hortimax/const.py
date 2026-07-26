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

#: Changed readouts reach the cloud within about a minute; unchanged ones are
#: refreshed at most every five. Each poll costs one request per controller,
#: so an organisation would need more than a hundred controllers before this
#: approached the documented limit of 100 requests per 15 seconds.
SCAN_INTERVAL: Final = 60  # seconds

# Unit identifiers that mean "dimensionless"; such readouts get no unit and
# no statistics (they are mostly status/override codes).
DIMENSIONLESS_UNITS: Final = {"Scalar", "None"}

# Readouts that report a time of day as seconds since (local) midnight, e.g.
# SunriseToday = 19145 -> 05:19. Home Assistant renders these far better as a
# timestamp than as a raw second count. Keyed by the lowercased identifier
# subject (the part before the '-kind' suffix, see naming.py).
TIME_OF_DAY_READOUTS: Final[frozenset[str]] = frozenset({"sunrisetoday", "sunsettoday"})

# Per-readout icon overrides, for readouts that have no device class (and thus
# no automatic icon) but read better with a hint. Keyed by the lowercased
# identifier subject (see naming.py). Absolute humidity is a g/kg mixing
# ratio, so it gets no humidity device class - just a friendlier icon.
READOUT_ICONS: Final[dict[str, str]] = {
    "absolutehumidity": "mdi:water-opacity",
    # Radiation sum (J/cm2) has no matching Home Assistant device class.
    "radiationsum": "mdi:sun-wireless",
    # Humidity deficit (g/kg moisture shortfall) has no matching device class
    # either - it is not a pressure, so the VPD/pressure classes do not apply.
    "humiditydeficit": "mdi:water-minus",
}

# CardinalWindDirection is an enumeration-coded Scalar readout: the value is
# a member id, not a bearing. aiohortos owns that table and turns an id into
# degrees; this constant only decides which readout gets the wind direction
# device class.
WIND_DIRECTION_SUBJECT: Final = "cardinalwinddirection"

# Maps HortOS unit identifiers to Home Assistant units of measurement.
# The first block is the complete set observed on a live HortOS Multima
# installation; the rest are plausible variants kept as aliases. Unknown
# identifiers fall back to the raw identifier string (without device class).
UNIT_MAP: Final[dict[str, str]] = {
    # Observed on a live system
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
    # Aliases / not yet observed
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

# Suggested display precision per mapped Home Assistant unit. Display-layer
# only: recorded states and statistics keep full precision. The API emits
# float32-converted doubles (e.g. 90.15303039550781 %), so every numeric
# sensor needs a sane default.
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

# Device classes that follow directly from the (mapped) unit. Cases that need
# the readout identifier as well (humidity, wind, gas, energy) are handled in
# sensor.py.
UNIT_DEVICE_CLASS: Final[dict[str, SensorDeviceClass]] = {
    UnitOfTemperature.CELSIUS: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.FAHRENHEIT: SensorDeviceClass.TEMPERATURE,
    UnitOfTemperature.KELVIN: SensorDeviceClass.TEMPERATURE,
    UnitOfIrradiance.WATTS_PER_SQUARE_METER: SensorDeviceClass.IRRADIANCE,
    UnitOfRatio.PARTS_PER_MILLION: SensorDeviceClass.CO2,
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

# pH deliberately has no device class: SensorDeviceClass.PH accepts no unit
# of measurement, and dropping the "pH" unit would be a worse trade than
# leaving the class off.

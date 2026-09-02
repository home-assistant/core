"""Constants for the Ridder HortiMaX Pro (HortOS) integration."""

import logging
from typing import Final

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

# Changed readouts are published about once a minute; unchanged ones keep a
# stale timestamp for up to five. One request per controller, limit 100/15s.
SCAN_INTERVAL: Final = 60  # seconds

# Dimensionless readouts are mostly status/override codes, so they get neither
# a unit nor statistics.
DIMENSIONLESS_UNITS: Final = {"Scalar", "None"}

# Seconds since local midnight (SunriseToday = 19145 -> 05:19), rendered as a
# timestamp. Keyed by the lowercased subject from `readout_subject()`.
TIME_OF_DAY_READOUTS: Final[frozenset[str]] = frozenset({"sunrisetoday", "sunsettoday"})
SECONDS_PER_DAY: Final = 24 * 60 * 60

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

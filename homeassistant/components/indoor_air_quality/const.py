"""Constants for the Indoor Air Quality integration."""

from typing import Final

from homeassistant.const import UnitOfDensity

# Base component constants
NAME: Final = "Indoor Air Quality"
DOMAIN: Final = "indoor_air_quality"

# Supported indoor air quality rating methodologies.
STANDARD_IAQUK_2015: Final = "iaquk_2015"
STANDARDS: Final = (STANDARD_IAQUK_2015,)
DEFAULT_STANDARD: Final = STANDARD_IAQUK_2015
CONF_STANDARD: Final = "standard"

SENSOR_INDEX: Final = "iaq_index"
SENSOR_LEVEL: Final = "iaq_level"

SENSOR_TYPES: Final = (SENSOR_INDEX, SENSOR_LEVEL)

# Configuration and options
CONF_SOURCES: Final = "sources"
CONF_TEMPERATURE: Final = "temperature"
CONF_HUMIDITY: Final = "humidity"
CONF_CO2: Final = "co2"
CONF_TVOC: Final = "tvoc"
CONF_VOC_INDEX: Final = "voc_index"
CONF_PM25: Final = "pm2_5"
CONF_NO2: Final = "no2"
CONF_CO: Final = "co"
CONF_HCHO: Final = "hcho"  # Formaldehyde
CONF_RADON: Final = "radon"

# Attributes
ATTR_LIMITING_SOURCE: Final = "limiting_source"
ATTR_SOURCES_SET: Final = "sources_set"
ATTR_SOURCES_USED: Final = "sources_used"
ATTR_SOURCE_INDEX_TPL: Final = "{}_index"


# Lowercase translation-key style level identifiers used as the
# ``iaq_level`` sensor's state. Display labels live in ``strings.json``.
LEVEL_EXCELLENT: Final = "excellent"
LEVEL_GOOD: Final = "good"
LEVEL_FAIR: Final = "fair"
LEVEL_POOR: Final = "poor"
LEVEL_INADEQUATE: Final = "inadequate"

LEVELS: Final = (
    LEVEL_EXCELLENT,
    LEVEL_GOOD,
    LEVEL_FAIR,
    LEVEL_POOR,
    LEVEL_INADEQUATE,
)

UNIT_PPM: Final = {
    "ppm": 1,  # Target unit -- conversion rate will be ignored
    "ppb": 0.001,
}
UNIT_PPB: Final = {
    "ppb": 1,  # Target unit -- conversion rate will be ignored
    "ppm": 1000,
}
UNIT_UGM3: Final = {
    # First entry is the target unit; remaining entries are aliases / sibling
    # units with their multiplicative factor to the target.
    UnitOfDensity.MICROGRAMS_PER_CUBIC_METER: 1,  # "μg/m³" (Greek mu)
    "µg/m³": 1,  # micro sign alias
    "µg/m3": 1,
    "µg/m^3": 1,
    "μg/m3": 1,  # Greek mu alias variants
    "μg/m^3": 1,
    "ug/m³": 1,
    "ug/m3": 1,
    "ug/m^3": 1,
    UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER: 1000,
    "mg/m3": 1000,
    "mg/m^3": 1000,
}
UNIT_MGM3: Final = {
    UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER: 1,  # Target unit
    "mg/m3": 1,
    "mg/m^3": 1,
    UnitOfDensity.MICROGRAMS_PER_CUBIC_METER: 0.001,
    "µg/m³": 0.001,
    "µg/m3": 0.001,
    "µg/m^3": 0.001,
    "μg/m3": 0.001,
    "μg/m^3": 0.001,
    "ug/m³": 0.001,
    "ug/m3": 0.001,
    "ug/m^3": 0.001,
}

# Molar masses (g/mol) used to convert between ppm/ppb and µg/m³ / mg/m³.
MOLAR_MASS_HCHO: Final = 30.0260
MOLAR_MASS_CO2: Final = 44.0100

from enum import Enum, StrEnum

from homeassistant.const import Platform

from homeassistant.components.climate.const import (
    PRESET_BOOST,
    PRESET_HOME,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_SLEEP,
    PRESET_ECO,
)

DOMAIN = "frisquet_connect"
DEVICE_MANUFACTURER = "Frisquet"
DEVICE_NAME = "Frisquet Connect"

# TODO : Check if for all platform there is at least one translation key & .py file
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]

### TRANSLATIONS KEYS
CLIMATE_TRANSLATIONS_KEY = "default_climate"

WATER_HEATER_TRANSLATIONS_KEY = "default_water_heater"

SENSOR_BOILER_LAST_UPDATE_TRANSLATIONS_KEY = "boiler_last_update"
SENSOR_CURRENT_BOILER_DATETIME_TRANSLATIONS_KEY = "current_boiler_datetime"
SENSOR_ALARM_TRANSLATIONS_KEY = "default_alarm"
SENSOR_INSIDE_THERMOMETER_TRANSLATIONS_KEY = "inside_thermometer"
SENSOR_OUTSIDE_THERMOMETER_TRANSLATIONS_KEY = "outside_thermometer"
SENSOR_HEATING_CONSUMPTION_TRANSLATIONS_KEY = "heating_consumption"
SENSOR_SANITARY_CONSUMPTION_TRANSLATIONS_KEY = "sanitary_consumption"


class ZoneModeLabelOrder(StrEnum):
    COMFORT = "CONS_CONF"
    REDUCED = "CONS_RED"
    FROST_PROTECTION = "CONS_HG"


SANITARY_WATER_ORDER_LABEL = "MODE_ECS"
SELECTOR_ORDER_LABEL = "SELECTEUR"
EXEMPTION_ORDER_LABEL = "MODE_DERO"
BOOST_ORDER_LABEL = "ACTIVITE_BOOST"

## ENUMS


class ConsumptionType(Enum):
    SANITARY = "SAN"
    HEATING = "CHF"


class AlarmType(StrEnum):
    NO_ALARM = "no_alarm"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


class SanitaryWaterType(Enum):
    WITHTOU_TANK = 0
    WITH_TANK = 1


class SanitaryWaterModeLabel(StrEnum):
    MAX = "Max"
    ECO = "Eco"
    ECO_TIMER = "Eco Timer"
    ECO_PLUS = "Eco+"
    ECO_PLUS_TIMER = "Eco+ Timer"
    STOP = "Stop"


class SanitaryWaterMode(Enum):
    MAX = 0  # "Max"
    ECO = 1  # "Eco"
    ECO_TIMER = 2  # "Eco Timer"
    ECO_PLUS = 3  # "Eco+"
    ECO_PLUS_TIMER = 4  # "Eco+ Timer"
    STOP = 5  # "Stop"


class ZoneMode(Enum):  # StrEnum ?
    COMFORT = 6
    REDUCED = 7
    FROST_PROTECTION = 8


class ZoneSelector(Enum):
    AUTO = 5
    COMFORT_PERMANENT = 6
    REDUCED_PERMANENT = 7
    FROST_PROTECTION = 8


PRESET_MODE_ORDERS_MAPPING = {
    PRESET_BOOST: {"key_order": BOOST_ORDER_LABEL, "mode": ZoneMode.COMFORT},
    PRESET_HOME: {"key_order": EXEMPTION_ORDER_LABEL, "mode": ZoneMode.COMFORT},
    PRESET_AWAY: {"key_order": EXEMPTION_ORDER_LABEL, "mode": ZoneMode.REDUCED},
    PRESET_COMFORT: {"key_order": SELECTOR_ORDER_LABEL, "mode": ZoneMode.COMFORT},
    PRESET_SLEEP: {"key_order": SELECTOR_ORDER_LABEL, "mode": ZoneMode.REDUCED},
    PRESET_ECO: {"key_order": SELECTOR_ORDER_LABEL, "mode": ZoneMode.FROST_PROTECTION},
}

"""Constants for the ViCare integration."""

import enum

from homeassistant.const import Platform

DOMAIN = "vicare"

SERVICE_GET_DHW_CIRCULATION_SCHEDULE = "get_dhw_circulation_schedule"
SERVICE_GET_DEVICE_RAW_FEATURES = "get_device_raw_features"
SERVICE_ACTIVATE_DHW_CIRCULATION_BOOST = "activate_dhw_circulation_boost"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]

UNSUPPORTED_DEVICES = [
    "Heatbox1",
    "Heatbox2_SRC",
    "E3_TCU10_x07",
    "E3_TCU41_x04",
    "E3_RoomControl_One_522",
]

VICARE_NAME = "ViCare"
VICARE_TOKEN_FILENAME = "vicare_token.save"

VIESSMANN_DEVELOPER_PORTAL = "https://app.developer.viessmann-climatesolutions.com"

CONF_CIRCUIT = "circuit"
CONF_HEATING_TYPE = "heating_type"
CONF_MIN_BOOST_TEMPERATURE = "min_boost_temperature"
CONF_HEAT_TIMEOUT_MINUTES = "heat_timeout_minutes"
CONF_WARM_WATER_DELAY_MINUTES = "warm_water_delay_minutes"

DEFAULT_CACHE_DURATION = 60
DEFAULT_DHW_BOOST_MIN_TEMPERATURE = 45.0
DEFAULT_DHW_BOOST_HEAT_TIMEOUT_MINUTES = 60
DEFAULT_DHW_BOOST_WARM_WATER_DELAY_MINUTES = 20

VICARE_BAR = "bar"
VICARE_CELSIUS = "celsius"
VICARE_CUBIC_METER = "cubicMeter"
VICARE_KW = "kilowatt"
VICARE_KWH = "kilowattHour"
VICARE_PERCENT = "percent"
VICARE_W = "watt"
VICARE_WH = "wattHour"


class HeatingType(enum.Enum):
    """Possible options for heating type."""

    auto = "auto"
    gas = "gas"
    oil = "oil"
    pellets = "pellets"
    heatpump = "heatpump"
    fuelcell = "fuelcell"
    hybrid = "hybrid"


DEFAULT_HEATING_TYPE = HeatingType.auto

HEATING_TYPE_TO_CREATOR_METHOD = {
    HeatingType.auto: "asAutoDetectDevice",
    HeatingType.gas: "asGazBoiler",
    HeatingType.fuelcell: "asFuelCell",
    HeatingType.heatpump: "asHeatPump",
    HeatingType.oil: "asOilBoiler",
    HeatingType.pellets: "asPelletsBoiler",
    HeatingType.hybrid: "asHybridDevice",
}

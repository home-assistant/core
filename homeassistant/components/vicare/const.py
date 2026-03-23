"""Constants for the ViCare integration."""

from homeassistant.const import Platform

DOMAIN = "vicare"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
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

DEFAULT_CACHE_DURATION = 60

VICARE_BAR = "bar"
VICARE_CELSIUS = "celsius"
VICARE_CUBIC_METER = "cubicMeter"
VICARE_KW = "kilowatt"
VICARE_KWH = "kilowattHour"
VICARE_PERCENT = "percent"
VICARE_W = "watt"
VICARE_WH = "wattHour"

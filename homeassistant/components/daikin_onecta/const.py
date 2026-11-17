"""Constants for Daikin Onecta."""

from daikin_onecta.client import ONECTA_API_URL

DOMAIN = "daikin_onecta"

OAUTH2_AUTHORIZE = "https://idp.onecta.daikineurope.com/v1/oidc/authorize"
OAUTH2_TOKEN = "https://idp.onecta.daikineurope.com/v1/oidc/token"
DAIKIN_API_URL = ONECTA_API_URL

# Daikin schedule names are limited to 32 characters, so this integration-only
# option cannot collide with a native schedule name.
SCHEDULE_DISABLED = "home_assistant_schedule_is_disabled"

FANMODE_FIXED = "fixed"

MANAGEMENT_POINT_DEVICE_TRANSLATION_KEYS = {
    "climateControl": "climate_zone",
    "domesticHotWaterFlowThrough": "domestic_hot_water_flow_through",
    "domesticHotWaterTank": "domestic_hot_water_tank",
    "indoorUnit": "indoor_unit",
    "indoorUnitHydro": "indoor_hydro_unit",
    "outdoorUnit": "outdoor_unit",
    "userInterface": "user_interface",
}

SENSORY_DATA_SENSOR_TYPES = (
    "roomTemperature",
    "outdoorTemperature",
    "leavingWaterTemperature",
    "tankTemperature",
    "roomHumidity",
    "pm1Concentration",
    "pm25Concentration",
    "pm10Concentration",
)

SENSOR_PERIOD_DAILY = "d"
SENSOR_PERIOD_WEEKLY = "w"
SENSOR_PERIOD_YEARLY = "m"
SENSOR_PERIOD_MONTHLY = "monthly"
SENSOR_PERIODS = {
    SENSOR_PERIOD_DAILY: "Daily",
    SENSOR_PERIOD_WEEKLY: "Weekly",
    SENSOR_PERIOD_MONTHLY: "Monthly",
    SENSOR_PERIOD_YEARLY: "Yearly",
}
SENSOR_PERIOD_UNIQUE_IDS = {
    SENSOR_PERIOD_DAILY: "daily",
    SENSOR_PERIOD_WEEKLY: "weekly",
    SENSOR_PERIOD_MONTHLY: "monthly",
    SENSOR_PERIOD_YEARLY: "yearly",
}

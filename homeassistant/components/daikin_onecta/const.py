"""Constants for Daikin Onecta."""

DOMAIN = "daikin_onecta"

OAUTH2_AUTHORIZE = "https://idp.onecta.daikineurope.com/v1/oidc/authorize"
OAUTH2_TOKEN = "https://idp.onecta.daikineurope.com/v1/oidc/token"

FANMODE_FIXED = "fixed"

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
ENERGY_AGGREGATE_PERIODS = {
    "day": SENSOR_PERIOD_DAILY,
    "week": SENSOR_PERIOD_WEEKLY,
    "year": SENSOR_PERIOD_YEARLY,
    "month": SENSOR_PERIOD_MONTHLY,
}

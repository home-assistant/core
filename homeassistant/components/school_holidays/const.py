"""Constants for the School Holidays integration."""

DOMAIN = "school_holidays"

UPDATE_INTERVAL_HOURS = 1

CONF_COUNTRY = "country"
DEFAULT_COUNTRY = "The Netherlands"
COUNTRIES = ["The Netherlands"]

CONF_REGION = "region"
REGIONS_NL = ["Noord", "Midden", "Zuid"]
REGIONS = {
    "The Netherlands": REGIONS_NL,
}

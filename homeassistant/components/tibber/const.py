"""Constants for Tibber integration."""

DATA_HASS_CONFIG = "tibber_hass_config"
DOMAIN = "tibber"
MANUFACTURER = "Tibber"
CONF_API_TYPE = "api_type"
API_TYPE_GRAPHQL = "graphql"
API_TYPE_DATA_API = "data_api"
DATA_API_DEFAULT_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "data-api-user-read",
    "data-api-chargers-read",
    "data-api-energy-systems-read",
    "data-api-homes-read",
    "data-api-thermostats-read",
    "data-api-vehicles-read",
    "data-api-inverters-read",
]

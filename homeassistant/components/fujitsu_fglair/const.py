"""Constants for the Fujitsu HVAC (based on Ayla IOT) integration."""

from datetime import timedelta

API_TIMEOUT = 10
API_REFRESH = timedelta(minutes=5)

DOMAIN = "fujitsu_fglair"

CONF_REGION = "region"
CONF_EUROPE = "is_europe"
REGION_EU = "EU"
REGION_DEFAULT = "default"

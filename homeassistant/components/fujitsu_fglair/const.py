"""Constants for the Fujitsu HVAC (based on Ayla IOT) integration."""

from datetime import timedelta

from ayla_iot_unofficial.fujitsu_consts import FGLAIR_APP_CREDENTIALS  # noqa: F401

API_TIMEOUT = 10
API_REFRESH = timedelta(minutes=5)

DOMAIN = "fujitsu_fglair"

CONF_REGION = "region"
CONF_REGION_DEFAULT = {"label": "other", "value": "default"}
CONF_REGION_EUROPE = {"label": "europe", "value": "EU"}
CONF_REGION_CHINA = {"label": "china", "value": "CN"}

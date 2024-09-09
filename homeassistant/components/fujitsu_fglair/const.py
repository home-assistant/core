"""Constants for the Fujitsu HVAC (based on Ayla IOT) integration."""

from datetime import timedelta

from ayla_iot_unofficial.fujitsu_consts import (  # noqa: F401
    FGLAIR_APP_ID,
    FGLAIR_APP_SECRET,
)

API_TIMEOUT = 10
API_REFRESH = timedelta(minutes=5)

DOMAIN = "fujitsu_fglair"

CONF_EUROPE = "is_europe"

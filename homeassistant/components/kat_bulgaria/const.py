"""Constants for the KAT Bulgaria integration."""

from datetime import timedelta

DOMAIN = "kat_bulgaria"

CONF_PERSON_EGN = "egn"
CONF_DRIVING_LICENSE = "driving_license_number"
CONF_PERSON_NAME = "person_name"

COORD_DATA_KEY = "obligations"

DEFAULT_POLL_INTERVAL = timedelta(minutes=30)

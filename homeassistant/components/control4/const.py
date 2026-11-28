"""Constants for the Control4 integration."""

from datetime import timedelta

DOMAIN = "control4"

SCAN_INTERVAL = timedelta(seconds=5)

API_RETRY_TIMES = 5

CONF_CONTROLLER_UNIQUE_ID = "controller_unique_id"

CONTROL4_ENTITY_TYPE = 7

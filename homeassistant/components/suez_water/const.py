"""Constants for the Suez Water integration."""

from datetime import timedelta

DOMAIN = "suez_water"

CONF_COUNTER_ID = "counter_id"

AGGREGATED_SENSOR_ENTITY_SUFFIX = "_water_usage_yesterday"

DATA_REFRESH_INTERVAL = timedelta(hours=12)

"""Store constants used across the integration."""

from datetime import timedelta

SERVICE_PARAM_DOMAIN_NAME = "domain"
SERVICE_PARAM_RECORD_NAME = "record"
SERVICE_PARAM_RECORD_VALUE = "value"
SERVICE_PARAM_RECORD_TYPE = "type"

MIN_TIME_BETWEEN_DOMAIN_UPDATES = timedelta(minutes=5)

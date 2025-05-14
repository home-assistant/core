"""Constants for the Paperless-ngx integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "paperless_ngx"

PLATFORMS: list[Platform] = [Platform.SENSOR]

LOGGER = logging.getLogger(__package__)

ENTITY_SENSOR_DOCUMENT_COUNT = "document_count"
ENTITY_SENSOR_INBOX_COUNT = "document_inbox_count"

ENTITY_SENSOR_STORAGE_TOTAL = "storage_total"
ENTITY_SENSOR_STORAGE_AVAILABLE = "storage_available"
ENTITY_SENSOR_STATUS_DATABASE = "status_database"
ENTITY_SENSOR_STATUS_REDIS = "status_redis"
ENTITY_SENSOR_STATUS_CELERY = "status_celery"
ENTITY_SENSOR_STATUS_INDEX = "status_index"
ENTITY_SENSOR_STATUS_CLASSIFIER = "status_classifier"

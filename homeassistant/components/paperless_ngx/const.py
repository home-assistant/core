"""Constants for the Paperless-ngx integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "paperless_ngx"

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

LOGGER = logging.getLogger(__package__)

CONF = "polling_interval"

ENTITY_SENSOR_DOCUMENTS_TOTAL = "documents_total"
ENTITY_SENSOR_DOCUMENTS_INBOX = "documents_inbox"
ENTITY_SENSOR_CHARACTERS_COUNT = "characters_count"

ENTITY_SENSOR_UPDATE_AVAILABLE = "update_available"
ENTITY_SENSOR_STORAGE_TOTAL = "storage_total"
ENTITY_SENSOR_STORAGE_AVAILABLE = "storage_available"
ENTITY_SENSOR_STATUS_DATABASE = "status_database"
ENTITY_SENSOR_STATUS_REDIS = "status_redis"
ENTITY_SENSOR_STATUS_CELERY = "status_celery"
ENTITY_SENSOR_STATUS_INDEX = "status_index"
ENTITY_SENSOR_STATUS_CLASSIFIER = "status_classifier"

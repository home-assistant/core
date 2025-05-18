"""Constants for the Paperless-ngx integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "paperless_ngx"

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

LOGGER = logging.getLogger(__package__)

REMOTE_VERSION_UPDATE_INTERVAL_HOURS = 24

ENTITY_SENSOR_DOCUMENTS_TOTAL = "documents_total"
ENTITY_SENSOR_DOCUMENTS_INBOX = "documents_inbox"
ENTITY_SENSOR_CHARACTERS_COUNT = "characters_count"
ENTITY_SENSOR_TAG_COUNT = "tag_count"
ENTITY_SENSOR_CORRESPONDENT_COUNT = "correspondent_count"
ENTITY_SENSOR_DOCUMENT_TYPE_COUNT = "document_type_count"

ENTITY_SENSOR_STORAGE_TOTAL = "storage_total"
ENTITY_SENSOR_STORAGE_AVAILABLE = "storage_available"
ENTITY_SENSOR_STATUS_DATABASE = "status_database"
ENTITY_SENSOR_STATUS_REDIS = "status_redis"
ENTITY_SENSOR_STATUS_CELERY = "status_celery"
ENTITY_SENSOR_STATUS_INDEX = "status_index"
ENTITY_SENSOR_STATUS_CLASSIFIER = "status_classifier"
ENTITY_SENSOR_STATUS_SANITY = "status_sanity"

ENTITY_BINARYSENSOR_UPDATE_AVAILABLE = "update_available"

ENTITY_ATTRIBUTE_ERROR = "error"
ENTITY_ATTRIBUTE_LAST_CHECKED = "last_checked"
ENTITY_ATTRIBUTE_LAST_RUN = "last_run"
ENTITY_ATTRIBUTE_LAST_MODIFIED = "last_modified"
ENTITY_ATTRIBUTE_LAST_TRAINED = "last_trained"
ENTITY_ATTRIBUTE_LATEST_VERSION = "lastest_version"

"""Constants for the Paperless-ngx integration."""

import logging

DOMAIN = "paperless_ngx"

LOGGER = logging.getLogger(__package__)

SENSOR_NAME_DOCUMENT_COUNT = "document_count"
SENSOR_NAME_INBOX_COUNT = "document_inbox_count"

DIAGNOSIS_NAME_STORAGE_TOTAL = "storage_total"
DIAGNOSIS_NAME_STORAGE_AVAILABLE = "storage_available"
DIAGNOSIS_NAME_STATUS_DATABASE = "status_database"
DIAGNOSIS_NAME_STATUS_REDIS = "status_redis"
DIAGNOSIS_NAME_STATUS_CELERY = "status_celery"
DIAGNOSIS_NAME_STATUS_INDEX = "status_index"
DIAGNOSIS_NAME_STATUS_CLASSIFIER = "status_classifier"

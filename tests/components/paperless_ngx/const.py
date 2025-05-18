"""Constants for the Paperless NGX integration tests."""

from pypaperless.models.common import StatusType

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_SCAN_INTERVAL

USER_INPUT = {
    CONF_HOST: "192.168.69.16",
    CONF_API_KEY: "test_token",
    CONF_SCAN_INTERVAL: 180,
}

PAPERLESS_IMPORT_PATHS = [
    "homeassistant.components.paperless_ngx.coordinator.Paperless",
    "homeassistant.components.paperless_ngx.Paperless",
    "homeassistant.components.paperless_ngx.config_flow.Paperless",
]

MOCK_STATUS_DATA = {
    "pngx_version": "2.2.1",
    "server_os": "Linux",
    "install_type": "docker",
    "storage": {
        "total": 5000000000,
        "available": 3200000000,
    },
    "database": {
        "type": "PostgreSQL",
        "url": "postgres://paperless@localhost:5432/db",
        "status": StatusType.OK.value,
        "error": None,
        "migration_status": {
            "latest_migration": "0010_auto_xyz",
            "unapplied_migrations": [],
        },
    },
    "tasks": {
        "redis_url": "redis://localhost:6379",
        "redis_status": StatusType.OK.value,
        "redis_error": None,
        "celery_status": StatusType.OK.value,
        "celery_url": "amqp://paperless:paperless@localhost:5672//",
        "celery_error": None,
        "index_status": StatusType.OK.value,
        "index_last_modified": "2024-05-18T12:00:00",
        "index_error": None,
        "classifier_status": StatusType.OK.value,
        "classifier_last_trained": "2024-05-01T00:00:00",
        "classifier_error": None,
        "sanity_check_status": StatusType.OK.value,
        "sanity_check_last_run": "2024-05-17T20:30:00",
        "sanity_check_error": None,
    },
}

MOCK_REMOTE_VERSION_DATA = {"version": "2.3.0", "update_available": True}

MOCK_STATISTICS_DATA = {
    "documents_total": 999,
    "documents_inbox": 9,
    "inbox_tag": 9,
    "inbox_tags": [9],
    "document_file_type_counts": [
        {"mime_type": "application/pdf", "mime_type_count": 998},
        {"mime_type": "image/png", "mime_type_count": 1},
    ],
    "character_count": 99999,
    "tag_count": 99,
    "correspondent_count": 99,
    "document_type_count": 99,
    "storage_path_count": 9,
    "current_asn": 99,
}

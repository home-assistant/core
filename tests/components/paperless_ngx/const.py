"""Constants for the Paperless NGX integration tests."""

from homeassistant.const import CONF_API_KEY, CONF_HOST

USER_INPUT = {
    CONF_HOST: "192.168.69.16",
    CONF_API_KEY: "test_token",
}

PAPERLESS_IMPORT_PATHS = [
    "homeassistant.components.paperless_ngx.coordinator.Paperless",
    "homeassistant.components.paperless_ngx.config_flow.Paperless",
]

MOCK_REMOTE_VERSION_DATA_NO_UPDATE = {"version": "2.3.0", "update_available": True}
MOCK_REMOTE_VERSION_DATA_UPDATE = {"version": "2.5.0", "update_available": True}
MOCK_REMOTE_VERSION_DATA_UNAVAILABLE = {"version": None, "update_available": None}
MOCK_REMOTE_VERSION_DATA_LIMIT_REACHED = {"version": "0.0.0", "update_available": True}

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

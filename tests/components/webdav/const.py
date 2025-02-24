"""Constants for WebDAV tests."""

from aiowebdav2 import Property

BACKUP_METADATA = {
    "addons": [],
    "backup_id": "23e64aec",
    "date": "2025-02-10T17:47:22.727189+01:00",
    "database_included": True,
    "extra_metadata": {},
    "folders": [],
    "homeassistant_included": True,
    "homeassistant_version": "2025.2.1",
    "name": "Automatic backup 2025.2.1",
    "protected": False,
    "size": 34519040,
}

MOCK_LIST_WITH_INFOS = [
    {
        "content_type": "application/x-tar",
        "created": "2025-02-10T17:47:22Z",
        "etag": '"84d7d000-62dcd4ce886b4"',
        "isdir": "False",
        "modified": "Mon, 10 Feb 2025 17:47:22 GMT",
        "name": "None",
        "path": "/Automatic_backup_2025.2.1_2025-02-10_18.31_30202686.tar",
        "size": "2228736000",
    },
    {
        "content_type": "application/json",
        "created": "2025-02-10T17:47:22Z",
        "etag": '"8d0-62dcd4cec050a"',
        "isdir": "False",
        "modified": "Mon, 10 Feb 2025 17:47:22 GMT",
        "name": "None",
        "path": "/Automatic_backup_2025.2.1_2025-02-10_18.31_30202686.metadata.json",
        "size": "2256",
    },
]

MOCK_GET_PROPERTY_METADATA_VERSION = Property(
    namespace="homeassistant",
    name="metadata_version",
    value="1",
)

MOCK_GET_PROPERTY_BACKUP_ID = Property(
    namespace="homeassistant",
    name="backup_id",
    value="23e64aec",
)

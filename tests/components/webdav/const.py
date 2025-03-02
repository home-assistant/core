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

MOCK_LIST_WITH_PROPERTIES = {
    "/Automatic_backup_2025.2.1_2025-02-10_18.31_30202686.tar": [],
    "/Automatic_backup_2025.2.1_2025-02-10_18.31_30202686.metadata.json": [
        Property(
            namespace="https://home-assistant.io",
            name="backup_id",
            value="23e64aec",
        ),
        Property(
            namespace="https://home-assistant.io",
            name="metadata_version",
            value="1",
        ),
    ],
}

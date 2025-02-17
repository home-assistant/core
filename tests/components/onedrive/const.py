"""Consts for OneDrive tests."""

from html import escape
from json import dumps

from onedrive_personal_sdk.const import DriveState, DriveType
from onedrive_personal_sdk.models.items import (
    AppRoot,
    Drive,
    DriveQuota,
    File,
    Folder,
    Hashes,
    IdentitySet,
    ItemParentReference,
    User,
)

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


BACKUP_METADATA = {
    "addons": [],
    "backup_id": "23e64aec",
    "date": "2024-11-22T11:48:48.727189+01:00",
    "database_included": True,
    "extra_metadata": {},
    "folders": [],
    "homeassistant_included": True,
    "homeassistant_version": "2024.12.0.dev0",
    "name": "Core 2024.12.0.dev0",
    "protected": False,
    "size": 34519040,
}

IDENTITY_SET = IdentitySet(
    user=User(
        display_name="John Doe",
        id="id",
        email="john@doe.com",
    )
)

MOCK_APPROOT = AppRoot(
    id="id",
    child_count=0,
    size=0,
    name="name",
    parent_reference=ItemParentReference(
        drive_id="mock_drive_id", id="id", path="path"
    ),
    created_by=IDENTITY_SET,
)

MOCK_BACKUP_FOLDER = Folder(
    id="id",
    name="name",
    size=0,
    child_count=0,
    parent_reference=ItemParentReference(
        drive_id="mock_drive_id", id="id", path="path"
    ),
    created_by=IDENTITY_SET,
)

MOCK_BACKUP_FILE = File(
    id="id",
    name="23e64aec.tar",
    size=34519040,
    parent_reference=ItemParentReference(
        drive_id="mock_drive_id", id="id", path="path"
    ),
    hashes=Hashes(
        quick_xor_hash="hash",
    ),
    mime_type="application/x-tar",
    description="",
    created_by=IDENTITY_SET,
)

MOCK_METADATA_FILE = File(
    id="id",
    name="23e64aec.tar",
    size=34519040,
    parent_reference=ItemParentReference(
        drive_id="mock_drive_id", id="id", path="path"
    ),
    hashes=Hashes(
        quick_xor_hash="hash",
    ),
    mime_type="application/x-tar",
    description=escape(
        dumps(
            {
                "metadata_version": 2,
                "backup_id": "23e64aec",
                "backup_file_id": "id",
            }
        )
    ),
    created_by=IDENTITY_SET,
)


MOCK_DRIVE = Drive(
    id="mock_drive_id",
    name="My Drive",
    drive_type=DriveType.PERSONAL,
    owner=IDENTITY_SET,
    quota=DriveQuota(
        deleted=5,
        remaining=805306368,
        state=DriveState.NEARING,
        total=5368709120,
        used=4250000000,
    ),
)

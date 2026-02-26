"""Tests for the syncthing integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL

URL = "http://127.0.0.1:8384"
TOKEN = "token"
VERIFY_SSL = True

MOCK_ENTRY = {
    CONF_URL: URL,
    CONF_TOKEN: TOKEN,
    CONF_VERIFY_SSL: VERIFY_SSL,
}

SERVER_ID = "YZXABCD-ABCDEFG-HIJKLMN-OPQRSTU-VWXYZAB-CDEFGHI-JKLMNOP-QRSTUVW"
SERVER_NAME = "This Device"
FOLDER_ID = "test-folder"
FOLDER_LABEL = "Test Folder"

SERVER_ID_SHORT = SERVER_ID.split("-", maxsplit=1)[0]
SERVER_NAME_HA = SERVER_NAME.lower().replace(" ", "_")
FOLDER_ID_HA = FOLDER_ID.lower().replace("-", "_")
FOLDER_LABEL_HA = FOLDER_LABEL.lower().replace(" ", "_")

SERVER_ENTITY_ID = f"sensor.{SERVER_ID_SHORT}_{SERVER_ID_SHORT}_{SERVER_NAME_HA}"
FOLDER_ENTITY_ID = f"sensor.{SERVER_ID_SHORT}_{FOLDER_ID_HA}_{FOLDER_LABEL_HA}"

MOCK_SYSTEM_STATUS = {"myID": SERVER_ID}

MOCK_SYSTEM_VERSION = {"version": "v1.23.0"}

MOCK_PING = {"ping": "pong"}

MOCK_CONFIG = {
    "folders": [
        {
            "id": FOLDER_ID,
            "label": FOLDER_LABEL,
        }
    ],
}

MOCK_FOLDER_STATUS = {
    "errors": 0,
    "globalBytes": 1000000,
    "globalDeleted": 0,
    "globalDirectories": 10,
    "globalFiles": 100,
    "globalSymlinks": 0,
    "globalTotalItems": 110,
    "ignorePatterns": False,
    "inSyncBytes": 1000000,
    "inSyncFiles": 100,
    "invalid": "",
    "localBytes": 1000000,
    "localDeleted": 0,
    "localDirectories": 10,
    "localFiles": 100,
    "localSymlinks": 0,
    "localTotalItems": 110,
    "needBytes": 0,
    "needDeletes": 0,
    "needDirectories": 0,
    "needFiles": 0,
    "needSymlinks": 0,
    "needTotalItems": 0,
    "pullErrors": 0,
    "state": "idle",
}

MOCK_FOLDER_SUMMARY_EVENT = {
    "id": 5,
    "globalID": 5,
    "type": "FolderSummary",
    "time": "2024-01-01T00:04:00.000000000Z",
    "data": {
        "folder": FOLDER_ID,
        "summary": {
            **MOCK_FOLDER_STATUS,
            "state": "syncing",
        },
    },
}

MOCK_STATE_CHANGED_EVENT = {
    "id": 6,
    "globalID": 6,
    "type": "StateChanged",
    "time": "2024-01-01T00:05:00.000000000Z",
    "data": {
        "folder": FOLDER_ID,
        "from": "idle",
        "to": "syncing",
    },
}

MOCK_FOLDER_PAUSED_EVENT = {
    "id": 7,
    "globalID": 7,
    "type": "FolderPaused",
    "time": "2024-01-01T00:06:00.000000000Z",
    "data": {
        "id": FOLDER_ID,
        "label": FOLDER_LABEL,
    },
}


def create_mock_syncthing_client() -> MagicMock:
    """Create a mocked Syncthing client."""
    mock_client = MagicMock()
    mock_system = MagicMock()
    mock_database = MagicMock()
    mock_events = MagicMock()

    mock_system.status = AsyncMock(return_value=MOCK_SYSTEM_STATUS)
    mock_system.version = AsyncMock(return_value=MOCK_SYSTEM_VERSION)
    mock_system.ping = AsyncMock(return_value=MOCK_PING)
    mock_system.config = AsyncMock(return_value=MOCK_CONFIG)
    mock_database.status = AsyncMock(return_value=MOCK_FOLDER_STATUS)

    async def mock_listen():
        """Mock events.listen that doesn't block."""
        while True:
            await asyncio.sleep(0)
            yield {
                "id": mock_events.last_seen_id,
                "type": "MockEvent",
            }

    mock_events.listen = mock_listen
    mock_events.last_seen_id = 0

    mock_client.system = mock_system
    mock_client.database = mock_database
    mock_client.events = mock_events

    mock_client.close = AsyncMock()

    return mock_client

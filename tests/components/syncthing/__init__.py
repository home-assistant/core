"""Tests for the syncthing integration."""

from unittest.mock import AsyncMock, MagicMock

from aiosyncthing.exceptions import SyncthingError

SERVER_ID = "YZXABCD-ABCDEFG-HIJKLMN-OPQRSTU-VWXYZAB-CDEFGHI-JKLMNOP-QRSTUVW"
SERVER_NAME = "This Device"
FOLDER_ID = "test-folder"
FOLDER_LABEL = "Test Folder"
DEVICE_ID = "ABCDEFG-HIJKLMN-OPQRSTU-VWXYZAB-CDEFGHI-JKLMNOP-QRSTUVW-XYZABCD"
DEVICE_NAME = "Test Device"

SERVER_ID_SHORT = SERVER_ID.split("-", maxsplit=1)[0]
SERVER_NAME_HA = SERVER_NAME.lower().replace(" ", "_")
DEVICE_ID_SHORT = DEVICE_ID.split("-", maxsplit=1)[0]
DEVICE_NAME_HA = DEVICE_NAME.lower().replace(" ", "_")
FOLDER_ID_HA = FOLDER_ID.lower().replace("-", "_")
FOLDER_LABEL_HA = FOLDER_LABEL.lower().replace(" ", "_")

FOLDER_ENTITY_ID = f"sensor.{SERVER_ID_SHORT}_{FOLDER_ID_HA}_{FOLDER_LABEL_HA}"
DEVICE_ENTITY_ID = f"sensor.{SERVER_ID_SHORT}_{DEVICE_ID_SHORT}_{DEVICE_NAME_HA}"
SERVER_ENTITY_ID = f"sensor.{SERVER_ID_SHORT}_{SERVER_ID_SHORT}_{SERVER_NAME_HA}"

MOCK_SYSTEM_STATUS = {"myID": SERVER_ID}

MOCK_SYSTEM_VERSION = {"version": "v1.23.0"}

MOCK_CONFIG = {
    "folders": [
        {
            "id": FOLDER_ID,
            "label": FOLDER_LABEL,
        }
    ],
    "devices": [
        {
            "deviceID": DEVICE_ID,
            "name": DEVICE_NAME,
        },
        {
            "deviceID": SERVER_ID,
            "name": SERVER_NAME,
        },
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

MOCK_CONFIG_DEVICE = {
    "deviceID": DEVICE_ID,
    "name": DEVICE_NAME,
    "addresses": ["dynamic"],
    "compression": "metadata",
    "certName": "",
    "introducer": False,
    "skipIntroductionRemovals": False,
    "introducedBy": "",
    "paused": False,
    "allowedNetworks": [],
    "autoAcceptFolders": False,
    "maxSendKbps": 0,
    "maxRecvKbps": 0,
    "ignoredFolders": [],
    "maxRequestKiB": 0,
    "untrusted": False,
    "remoteGUIPort": 0,
}

MOCK_CONFIG_SERVER = {
    "deviceID": SERVER_ID,
    "name": SERVER_NAME,
    "addresses": ["dynamic"],
    "compression": "metadata",
    "certName": "",
    "introducer": False,
    "skipIntroductionRemovals": False,
    "introducedBy": "",
    "paused": False,
    "allowedNetworks": [],
    "autoAcceptFolders": False,
    "maxSendKbps": 0,
    "maxRecvKbps": 0,
    "ignoredFolders": [],
    "maxRequestKiB": 0,
    "untrusted": False,
    "remoteGUIPort": 0,
}

MOCK_DEVICE_CONNECTED_EVENT = {
    "id": 1,
    "globalID": 1,
    "type": "DeviceConnected",
    "time": "2024-01-01T00:00:00.000000000Z",
    "data": {
        "addr": "192.168.1.100:22000",
        "deviceName": DEVICE_NAME,
        "clientName": "syncthing",
        "clientVersion": "v1.23.0",
        "type": "tcp-client",
        "id": DEVICE_ID,
    },
}

MOCK_DEVICE_DISCONNECTED_EVENT = {
    "id": 2,
    "globalID": 2,
    "type": "DeviceDisconnected",
    "time": "2024-01-01T00:01:00.000000000Z",
    "data": {
        "error": "EOF",
        "id": DEVICE_ID,
    },
}

MOCK_DEVICE_PAUSED_EVENT = {
    "id": 3,
    "globalID": 3,
    "type": "DevicePaused",
    "time": "2024-01-01T00:02:00.000000000Z",
    "data": {
        "device": DEVICE_ID,
    },
}

MOCK_DEVICE_RESUMED_EVENT = {
    "id": 4,
    "globalID": 4,
    "type": "DeviceResumed",
    "time": "2024-01-01T00:03:00.000000000Z",
    "data": {
        "device": DEVICE_ID,
    },
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


def create_mock_syncthing_client(
    raise_connection_error: bool = False,
) -> MagicMock:
    """Create a mocked Syncthing client."""
    mock_client = MagicMock()
    mock_system = MagicMock()
    mock_config = MagicMock()
    mock_database = MagicMock()
    mock_events = MagicMock()

    if raise_connection_error:
        for mock in (
            mock_system.status,
            mock_system.version,
            mock_system.config,
            mock_config.devices,
            mock_database.status,
            mock_events.last_seen_id,
            mock_events.listen,
        ):
            mock.side_effect = SyncthingError("Connection error")
    else:
        mock_system.status = AsyncMock(return_value=MOCK_SYSTEM_STATUS)
        mock_system.version = AsyncMock(return_value=MOCK_SYSTEM_VERSION)
        mock_system.config = AsyncMock(return_value=MOCK_CONFIG)

        async def devices_side_effect(device_id: str):
            if device_id == DEVICE_ID:
                return MOCK_CONFIG_DEVICE
            if device_id == SERVER_ID:
                return MOCK_CONFIG_SERVER
            raise KeyError(device_id)

        mock_config.devices = AsyncMock(side_effect=devices_side_effect)
        mock_database.status = AsyncMock(return_value=MOCK_FOLDER_STATUS)

        # Create async generator for events.listen
        async def mock_listen():
            """Mock events.listen that doesn't block."""
            while False:
                yield

        mock_events.listen = mock_listen
        mock_events.last_seen_id = 0

    # Assign sub-clients
    mock_client.system = mock_system
    mock_client.config = mock_config
    mock_client.database = mock_database
    mock_client.events = mock_events

    # Other methods
    mock_client.close = AsyncMock()

    return mock_client

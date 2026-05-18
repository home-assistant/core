"""Tests for the syncthing integration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.syncthing.const import DOMAIN
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL

from tests.common import load_json_object_fixture

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

SERVER_ID_SHORT_HA = SERVER_ID.split("-", maxsplit=1)[0].lower()
URL_HA = URL.lower().replace("://", "_").replace(".", "_").replace(":", "_")

SERVER_ENTITY_ID = f"sensor.syncthing_{URL_HA}_{SERVER_ID_SHORT_HA}_{SERVER_ID_SHORT_HA}_{SERVER_NAME.lower().replace(' ', '_')}"
FOLDER_ENTITY_ID = f"sensor.syncthing_{URL_HA}_{SERVER_ID_SHORT_HA}_{FOLDER_ID.lower().replace('-', '_')}_{FOLDER_LABEL.lower().replace(' ', '_')}"

MOCK_SYSTEM_STATUS = load_json_object_fixture("system_status.json", DOMAIN)
MOCK_SYSTEM_VERSION = load_json_object_fixture("system_version.json", DOMAIN)
MOCK_PING = load_json_object_fixture("ping.json", DOMAIN)
MOCK_CONFIG = load_json_object_fixture("config.json", DOMAIN)
MOCK_FOLDER_STATUS = load_json_object_fixture("folder_status.json", DOMAIN)
MOCK_FOLDER_SUMMARY_EVENT = load_json_object_fixture(
    "folder_summary_event.json", DOMAIN
)
MOCK_STATE_CHANGED_EVENT = load_json_object_fixture("state_changed_event.json", DOMAIN)
MOCK_FOLDER_PAUSED_EVENT = load_json_object_fixture("folder_paused_event.json", DOMAIN)


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
            await asyncio.sleep(3600)
            yield None

    mock_events.listen = mock_listen
    mock_events.last_seen_id = 0

    mock_client.system = mock_system
    mock_client.database = mock_database
    mock_client.events = mock_events

    mock_client.close = AsyncMock()
    mock_client.url = URL

    return mock_client

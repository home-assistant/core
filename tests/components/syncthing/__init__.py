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
DEVICE_ID = "ABCDEFG-HIJKLMN-OPQRSTU-VWXYZAB-CDEFGHI-JKLMNOP-QRSTUVW-XYZABCD"
DEVICE_NAME = "Test Device"
FOLDER_ID = "test-folder"
FOLDER_LABEL = "Test Folder"

SERVER_ID_SHORT_HA = SERVER_ID.split("-", maxsplit=1)[0]
URL_HA = URL.lower().replace("://", "_").replace(".", "_").replace(":", "_")


def create_mock_syncthing_client() -> MagicMock:
    """Create a mocked Syncthing client."""
    mock_client = MagicMock()
    mock_config = MagicMock()
    mock_system = MagicMock()
    mock_database = MagicMock()
    mock_events = MagicMock()

    mock_system.status = AsyncMock(
        return_value=load_json_object_fixture("system_status.json", DOMAIN)
    )
    mock_system.version = AsyncMock(
        return_value=load_json_object_fixture("system_version.json", DOMAIN)
    )
    mock_system.ping = AsyncMock(
        return_value=load_json_object_fixture("ping.json", DOMAIN)
    )
    mock_system.config = AsyncMock(
        return_value=load_json_object_fixture("config.json", DOMAIN)
    )
    mock_database.status = AsyncMock(
        return_value=load_json_object_fixture("folder_status.json", DOMAIN)
    )

    def devices_side_effect(device_id: str) -> dict[str, object]:
        """Return device config based on device ID."""
        if device_id == DEVICE_ID:
            return load_json_object_fixture("device_config.json", DOMAIN)
        if device_id == SERVER_ID:
            return load_json_object_fixture("server_config.json", DOMAIN)
        raise KeyError(device_id)

    mock_config.devices = AsyncMock(side_effect=devices_side_effect)

    async def mock_listen():
        """Mock events.listen that doesn't block."""
        while True:
            await asyncio.sleep(3600)
            yield None

    mock_events.listen = mock_listen
    mock_events.last_seen_id = 0

    mock_client.system = mock_system
    mock_client.config = mock_config
    mock_client.database = mock_database
    mock_client.events = mock_events

    mock_client.close = AsyncMock()
    mock_client.url = URL

    return mock_client

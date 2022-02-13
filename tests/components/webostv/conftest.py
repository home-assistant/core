"""Common fixtures and objects for the LG webOS integration tests."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.webostv.const import LIVE_TV_APP_ID
from homeassistant.helpers import entity_registry

from .const import CHANNEL_1, CHANNEL_2, CLIENT_KEY, FAKE_UUID, MOCK_APPS, MOCK_INPUTS

from tests.common import async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.webostv.WebOsClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.hello_info = {"deviceUUID": FAKE_UUID}
        client.software_info = {"major_ver": "major", "minor_ver": "minor"}
        client.system_info = {"modelName": "TVFAKE"}
        client.client_key = CLIENT_KEY
        client.apps = MOCK_APPS
        client.inputs = MOCK_INPUTS
        client.current_app_id = LIVE_TV_APP_ID

        client.channels = [CHANNEL_1, CHANNEL_2]
        client.current_channel = CHANNEL_1

        client.volume = 37
        client.sound_output = "speaker"
        client.muted = False
        client.is_on = True

        async def mock_state_update_callback():
            await client.register_state_update_callback.call_args[0][0](client)

        client.mock_state_update = AsyncMock(side_effect=mock_state_update_callback)

        yield client


@pytest.fixture(name="client_entity_removed")
def client_entity_removed_fixture(hass):
    """Patch of client library, entity removed waiting for connect."""
    with patch(
        "homeassistant.components.webostv.WebOsClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.hello_info = {"deviceUUID": FAKE_UUID}
        client.connected = False

        def mock_is_connected():
            return client.connected

        client.is_connected = Mock(side_effect=mock_is_connected)

        async def mock_connected():
            ent_reg = entity_registry.async_get(hass)
            ent_reg.async_remove("media_player.webostv_some_secret")
            client.connected = True

        client.connect = AsyncMock(side_effect=mock_connected)

        yield client

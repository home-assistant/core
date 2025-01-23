"""Common fixtures and objects for the LG webOS integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.webostv.const import LIVE_TV_APP_ID

from .const import (
    CHANNEL_1,
    CHANNEL_2,
    CLIENT_KEY,
    FAKE_UUID,
    MOCK_APPS,
    MOCK_INPUTS,
    TV_MODEL,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.webostv.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.webostv.WebOsClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.hello_info = {"deviceUUID": FAKE_UUID}
        client.software_info = {"major_ver": "major", "minor_ver": "minor"}
        client.system_info = {"modelName": TV_MODEL}
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
        client.is_registered = Mock(return_value=True)
        client.is_connected = Mock(return_value=True)

        async def mock_state_update_callback():
            await client.register_state_update_callback.call_args[0][0](client)

        client.mock_state_update = AsyncMock(side_effect=mock_state_update_callback)

        yield client

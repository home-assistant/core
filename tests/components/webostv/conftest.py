"""Common fixtures and objects for the LG webOS TV integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from aiowebostv import WebOsTvInfo, WebOsTvState
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
    with (
        patch(
            "homeassistant.components.webostv.WebOsClient", autospec=True
        ) as mock_client_class,
        patch(
            "homeassistant.components.webostv.config_flow.WebOsClient",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.tv_info = WebOsTvInfo(
            hello={"deviceUUID": FAKE_UUID},
            system={"modelName": TV_MODEL, "serialNumber": "1234567890"},
            software={"major_ver": "major", "minor_ver": "minor"},
        )
        client.client_key = CLIENT_KEY
        client.tv_state = WebOsTvState(
            apps=MOCK_APPS,
            inputs=MOCK_INPUTS,
            current_app_id=LIVE_TV_APP_ID,
            channels=[CHANNEL_1, CHANNEL_2],
            current_channel=CHANNEL_1,
            volume=37,
            sound_output="speaker",
            muted=False,
            is_on=True,
            media_state=[{"playState": ""}],
        )

        client.is_registered = Mock(return_value=True)
        client.is_connected = Mock(return_value=True)

        async def mock_state_update_callback():
            await client.register_state_update_callback.call_args[0][0](client.tv_state)

        client.mock_state_update = AsyncMock(side_effect=mock_state_update_callback)

        yield client

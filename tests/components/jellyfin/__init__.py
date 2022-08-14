"""Tests for the jellyfin integration."""

from typing import Any
from unittest.mock import MagicMock, Mock, patch

from homeassistant.components.jellyfin.const import (
    DATA_CLIENT,
    DOMAIN,
    MAX_STREAMING_BITRATE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_AUTH_TOKEN,
    MOCK_DEVICE_ID,
    MOCK_SUCCESFUL_CONNECTION_STATE,
    MOCK_SUCCESFUL_LOGIN_RESPONSE,
    MOCK_TRACK,
    MOCK_TRACK_ID,
    MOCK_USER_ID,
    TEST_PASSWORD,
    TEST_URL,
    TEST_USERNAME,
)

from tests.common import MockConfigEntry


def create_mock_jellyfin_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Add a test config entry."""
    config_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        title=f"{TEST_URL}",
    )
    config_entry.add_to_hass(hass)
    return config_entry


def _create_mock_jellyfin_api() -> Mock:
    """Create a mock Jellyfin api."""
    api = Mock()
    api.audio_url = Mock(side_effect=_audio_url)
    api.get_item = Mock(side_effect=_select_return_item)

    return api


def _select_return_item(item_id: str) -> dict[str, Any]:
    """Return a mock item based on item id."""
    if item_id == MOCK_TRACK_ID:
        return MOCK_TRACK


def _audio_url(item_id: str) -> str:
    """Return streaming url based on item id."""
    return f"{TEST_URL}/Audio/{item_id}/universal?UserId={MOCK_USER_ID}&DeviceId=Home+Assistant&api_key={MOCK_AUTH_TOKEN}&MaxStreamingBitrate={MAX_STREAMING_BITRATE}"


def _create_mock_jellyfin_connection_manager(
    connection_side_effect: Any = None, login_side_effect: Any = None
) -> Mock:
    """Return a mock Jellyfin connection manager."""
    connection_manager = Mock()
    if connection_side_effect:
        connection_manager.connect_to_address = Mock(side_effect=connection_side_effect)
    else:
        connection_manager.connect_to_address = Mock(
            return_value=MOCK_SUCCESFUL_CONNECTION_STATE
        )
    if login_side_effect:
        connection_manager.login = Mock(side_effect=login_side_effect)
    else:
        connection_manager.login = Mock(return_value=MOCK_SUCCESFUL_LOGIN_RESPONSE)

    return connection_manager


def create_mock_jellyfin_client(
    connection_side_effect: Any = None, login_side_effect: Any = None
) -> Mock:
    """Create mock Jellyfin client."""
    jellyfin_client = MagicMock()
    jellyfin_client.jellyfin = _create_mock_jellyfin_api()
    jellyfin_client.auth = _create_mock_jellyfin_connection_manager(
        connection_side_effect, login_side_effect
    )
    jellyfin_client.config.data = {
        "auth.user_id": MOCK_USER_ID,
        "app.device_id": MOCK_DEVICE_ID,
        "auth.token": MOCK_AUTH_TOKEN,
        "auth.server": TEST_URL,
    }

    return jellyfin_client


async def setup_mock_jellyfin_config_entry(
    hass: HomeAssistant,
    connection_side_effect: Any = None,
    login_side_effect: Any = None,
) -> ConfigEntry:
    """Create a mock Jellyfin config entry."""

    config_entry = create_mock_jellyfin_config_entry(hass)
    client = create_mock_jellyfin_client(connection_side_effect, login_side_effect)

    with patch(
        "homeassistant.components.jellyfin.create_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    hass.data[DOMAIN][config_entry.entry_id] = {DATA_CLIENT: client}

    return config_entry

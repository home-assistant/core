"""Fixtures for Jellyfin integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from jellyfin_apiclient_python import JellyfinClient
from jellyfin_apiclient_python.api import API
from jellyfin_apiclient_python.configuration import Config
from jellyfin_apiclient_python.connection_manager import ConnectionManager
import pytest

from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import load_json_fixture
from .const import TEST_PASSWORD, TEST_URL, TEST_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Jellyfin",
        domain=DOMAIN,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        unique_id="USER-UUID",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.jellyfin.async_setup_entry", return_value=True
    ) as setup_mock:
        yield setup_mock


@pytest.fixture
def mock_client_device_id() -> Generator[None, MagicMock, None]:
    """Mock generating device id."""
    with patch(
        "homeassistant.components.jellyfin.config_flow._generate_client_device_id"
    ) as id_mock:
        id_mock.return_value = "TEST-UUID"
        yield id_mock


@pytest.fixture
def mock_auth() -> MagicMock:
    """Return a mocked ConnectionManager."""
    jf_auth = create_autospec(ConnectionManager)
    jf_auth.connect_to_address.return_value = load_json_fixture(
        "auth-connect-address.json"
    )
    jf_auth.login.return_value = load_json_fixture("auth-login.json")

    return jf_auth


@pytest.fixture
def mock_api() -> MagicMock:
    """Return a mocked API."""
    jf_api = create_autospec(API)
    jf_api.get_user_settings.return_value = load_json_fixture("get-user-settings.json")
    jf_api.sessions.return_value = load_json_fixture("sessions.json")

    jf_api.artwork.side_effect = api_artwork_side_effect
    jf_api.audio_url.side_effect = api_audio_url_side_effect
    jf_api.video_url.side_effect = api_video_url_side_effect
    jf_api.user_items.side_effect = api_user_items_side_effect
    jf_api.get_item.side_effect = api_get_item_side_effect
    jf_api.get_media_folders.return_value = load_json_fixture("get-media-folders.json")
    jf_api.user_items.side_effect = api_user_items_side_effect

    return jf_api


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mocked JellyfinClient."""
    jf_config = create_autospec(Config)
    jf_config.data = {"auth.server": "http://localhost"}

    return jf_config


@pytest.fixture
def mock_client(
    mock_config: MagicMock, mock_auth: MagicMock, mock_api: MagicMock
) -> MagicMock:
    """Return a mocked JellyfinClient."""
    jf_client = create_autospec(JellyfinClient)
    jf_client.auth = mock_auth
    jf_client.config = mock_config
    jf_client.jellyfin = mock_api

    return jf_client


@pytest.fixture
def mock_jellyfin(mock_client: MagicMock) -> Generator[None, MagicMock, None]:
    """Return a mocked Jellyfin."""
    with patch(
        "homeassistant.components.jellyfin.client_wrapper.Jellyfin", autospec=True
    ) as jellyfin_mock:
        jf = jellyfin_mock.return_value
        jf.get_client.return_value = mock_client

        yield jf


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_jellyfin: MagicMock
) -> MockConfigEntry:
    """Set up the Jellyfin integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


def api_artwork_side_effect(*args, **kwargs):
    """Handle variable responses for artwork method."""
    item_id = args[0]
    art = args[1]
    ext = "jpg"

    return f"http://localhost/Items/{item_id}/Images/{art}.{ext}"


def api_audio_url_side_effect(*args, **kwargs):
    """Handle variable responses for audio_url method."""
    item_id = args[0]
    return f"http://localhost/Audio/{item_id}/universal?UserId=test-username,DeviceId=TEST-UUID,MaxStreamingBitrate=140000000"


def api_video_url_side_effect(*args, **kwargs):
    """Handle variable responses for video_url method."""
    item_id = args[0]
    return f"http://localhost/Videos/{item_id}/stream?static=true,DeviceId=TEST-UUID,api_key=TEST-API-KEY"


def api_get_item_side_effect(*args):
    """Handle variable responses for get_item method."""
    return load_json_fixture("get-item-collection.json")


def api_user_items_side_effect(*args, **kwargs):
    """Handle variable responses for items  method."""
    params = kwargs.get("params", {}) if kwargs else {}

    if "parentId" in params:
        return load_json_fixture("user-items-parent-id.json")

    return load_json_fixture("user-items.json")

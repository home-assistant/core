"""Test slack notifications."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from aiohttp.client_exceptions import ClientError
import pytest
from slack.errors import SlackApiError

from homeassistant.components import notify
from homeassistant.components.slack import DATA_CLIENT, DOMAIN, SLACK_DATA
from homeassistant.components.slack.notify import (
    CONF_DEFAULT_CHANNEL,
    SlackNotificationService,
    _async_process_target,
    async_get_service,
)
from homeassistant.const import ATTR_ICON, CONF_API_KEY, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import CONF_DATA

SERVICE_NAME = f"notify_{DOMAIN}"

DEFAULT_CONFIG = {
    notify.DOMAIN: [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: SERVICE_NAME,
            CONF_API_KEY: "12345",
            CONF_DEFAULT_CHANNEL: "channel",
        }
    ]
}


@pytest.fixture
def mock_client():
    """Create a mock Slack client."""
    client = Mock()
    client.chat_postMessage = AsyncMock(return_value={"ok": True})
    client.conversations_list = AsyncMock(
        return_value={
            "ok": True,
            "channels": [
                {"name": "general", "id": "C111"},
                {"name": "random", "id": "C222"},
            ],
        }
    )
    client.conversations_open = AsyncMock(
        return_value={"ok": True, "channel": {"id": "D111"}}
    )
    client.files_upload_v2 = AsyncMock(return_value={"ok": True})
    return client


@pytest.fixture(autouse=True)
def hass_mock(hass: HomeAssistant):
    """Mock hass for allowing external URLs."""
    hass.config.is_allowed_external_url = Mock(return_value=True)
    return hass


async def test_message_includes_default_emoji(mock_client) -> None:
    """Tests that default icon is used when no message icon is given."""
    expected_icon = ":robot_face:"
    service = SlackNotificationService(
        None, mock_client, CONF_DATA | {ATTR_ICON: expected_icon}
    )

    await service.async_send_message("test", target="C123456789")

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_emoji"] == expected_icon


async def test_targets_channel_name(mock_client) -> None:
    """Test sending message to channel by name."""
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    await service.async_send_message("test", target="#general")

    # Should only call conversations_list for public and private channels once each
    assert mock_client.conversations_list.call_count == 2
    mock_client.chat_postMessage.assert_called_once_with(
        link_names=True, text="test", channel="C111"
    )


async def test_targets_channel_id(mock_client) -> None:
    """Test sending message to channel by ID."""
    service = SlackNotificationService(None, mock_client, CONF_DATA)
    channel_id = "C123456789"

    await service.async_send_message("test", target=channel_id)

    # Should not need to resolve channel ID
    mock_client.conversations_list.assert_not_called()
    mock_client.chat_postMessage.assert_called_once_with(
        link_names=True, text="test", channel=channel_id
    )


async def test_targets_user_id(mock_client) -> None:
    """Test sending message to user by ID."""
    service = SlackNotificationService(None, mock_client, CONF_DATA)
    user_id = "U123456789"

    await service.async_send_message("test", target=user_id)

    # Should get DM channel ID via conversations_open
    mock_client.conversations_open.assert_called_once_with(users=[user_id])
    mock_client.chat_postMessage.assert_called_once_with(
        link_names=True, text="test", channel="D111"
    )


async def test_targets_multiple(mock_client) -> None:
    """Test sending message to multiple targets."""
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    await service.async_send_message(
        "test", target=["#general", "C123456789", "U123456789"]
    )

    # Should resolve channel name and user ID, but not channel ID
    assert mock_client.conversations_list.call_count == 2  # public and private
    assert mock_client.conversations_open.call_count == 1
    assert mock_client.chat_postMessage.call_count == 3


async def test_target_resolution_failure(mock_client) -> None:
    """Test handling of target resolution failures."""
    mock_client.conversations_list.return_value = {"ok": False, "error": "error"}
    mock_client.conversations_open.return_value = {"ok": False, "error": "error"}

    service = SlackNotificationService(None, mock_client, CONF_DATA)

    with pytest.raises(HomeAssistantError) as excinfo:
        await service.async_send_message(
            "test", target=["#nonexistent", "INVALID", "U123456789"]
        )
    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "error_channel_not_found"
    assert excinfo.value.translation_placeholders == {"channel_name": "nonexistent"}

    # No successful message sends due to resolution failures
    assert mock_client.chat_postMessage.call_count == 0


async def test_file_upload_targets(mock_client, hass_mock) -> None:
    """Test file upload with different target types."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.read = AsyncMock(return_value=b"file content")

    with patch(
        "homeassistant.components.slack.notify.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        service = SlackNotificationService(hass_mock, mock_client, CONF_DATA)

        await service.async_send_message(
            "test",
            target=["#general", "U123456789"],
            data={"file": {"url": "http://example.com/image.jpg"}},
        )

        # Should resolve targets and call files_upload_v2 once with all resolved channel IDs
        assert mock_client.conversations_list.call_count == 2
        assert mock_client.conversations_open.call_count == 1
        assert mock_client.files_upload_v2.call_count == 2


async def test_remote_file_not_allowed(hass_mock, mock_client) -> None:
    """Test uploading a remote file from a non-allowed URL."""
    hass_mock.config.is_allowed_external_url = Mock(return_value=False)
    service = SlackNotificationService(hass_mock, mock_client, CONF_DATA)

    await service.async_send_message(
        "test", data={"file": {"url": "http://example.com/not-allowed.jpg"}}
    )

    mock_client.files_upload_v2.assert_not_called()


async def test_remote_file_download_error(mock_client, hass_mock) -> None:
    """Test handling of remote file download errors."""
    with patch(
        "homeassistant.components.slack.notify.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value.get.side_effect = ClientError()

        service = SlackNotificationService(hass_mock, mock_client, CONF_DATA)

        await service.async_send_message(
            "test", data={"file": {"url": "http://example.com/error.jpg"}}
        )

        mock_client.files_upload_v2.assert_not_called()


async def test_slack_api_errors(mock_client) -> None:
    """Test handling of Slack API errors."""
    mock_client.chat_postMessage.side_effect = SlackApiError("error", {"ok": False})
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    # Should not raise an exception
    await service.async_send_message("test", target="C123456789")


async def test_conversation_list_error(mock_client) -> None:
    """Test handling of conversation list errors."""
    mock_client.conversations_list.side_effect = SlackApiError("error", {"ok": False})
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    with pytest.raises(HomeAssistantError) as excinfo:
        await service.async_send_message("test", target="#some-channel")

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "error_getting_channel"
    assert excinfo.value.translation_placeholders == {
        "channel_name": "some-channel",
        "error": "error\nThe server responded with: {'ok': False}",
    }

    mock_client.chat_postMessage.assert_not_called()


async def test_channel_not_found(mock_client) -> None:
    """Test handling of non-existent channel."""
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    with pytest.raises(HomeAssistantError) as excinfo:
        await service.async_send_message("test", target="#nonexistent")

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "error_channel_not_found"
    assert excinfo.value.translation_placeholders == {"channel_name": "nonexistent"}

    mock_client.chat_postMessage.assert_not_called()


async def test_file_upload_with_auth(mock_client, hass_mock) -> None:
    """Test file upload with basic auth credentials."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.read = AsyncMock(return_value=b"file content")

    with patch(
        "homeassistant.components.slack.notify.aiohttp_client.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        service = SlackNotificationService(hass_mock, mock_client, CONF_DATA)

        await service.async_send_message(
            "test",
            target="#general",  # Added explicit target
            data={
                "file": {
                    "url": "http://example.com/image.jpg",
                    "username": "user",
                    "password": "pass",
                }
            },
        )

        # Verify auth was used
        mock_session.return_value.get.assert_called_once()
        kwargs = mock_session.return_value.get.call_args.kwargs
        assert "auth" in kwargs

        # Verify file upload
        assert (
            mock_client.files_upload_v2.call_count == 1
        )  # Changed to handle one upload per channel


async def test_get_service_discovery_info(hass: HomeAssistant) -> None:
    """Test async_get_service with discovery info."""
    mock_client = AsyncMock()
    discovery_info = {SLACK_DATA: {DATA_CLIENT: mock_client}}

    service = await async_get_service(hass, {}, discovery_info)

    assert service is not None
    assert isinstance(service, SlackNotificationService)
    assert service._client == mock_client
    assert service._hass == hass
    assert service._config == discovery_info


async def test_get_service_no_discovery_info(hass: HomeAssistant) -> None:
    """Test async_get_service without discovery info."""
    service = await async_get_service(hass, {}, None)
    assert service is None


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        # Empty/None handling
        ("", ("channel_name", "")),
        # User IDs
        ("U123ABC456", ("user_id", "U123ABC456")),
        ("W123ABC456", ("user_id", "W123ABC456")),
        ("UABCDEF123", ("user_id", "UABCDEF123")),
        # Channel IDs
        ("C123ABC456", ("channel_id", "C123ABC456")),
        ("G123ABC456", ("channel_id", "G123ABC456")),
        ("D123ABC456", ("channel_id", "D123ABC456")),
        # Channel names
        ("general", ("channel_name", "general")),
        ("#general", ("channel_name", "general")),
        ("my-channel", ("channel_name", "my-channel")),
        ("#my-channel", ("channel_name", "my-channel")),
        # Invalid/Edge cases
        ("U12345", ("channel_name", "U12345")),  # Too short for user ID
        ("C12345", ("channel_name", "C12345")),  # Too short for channel ID
        ("X123ABC456", ("channel_name", "X123ABC456")),  # Invalid prefix
        ("U123ABC456DEF", ("user_id", "U123ABC456DEF")),  # Extra long but valid
        ("not-an-id", ("channel_name", "not-an-id")),
    ],
)
def test_process_target(target: str, expected: tuple[str, str]) -> None:
    """Test target processing for various input formats."""
    assert _async_process_target(target) == expected


def test_process_target_not_string() -> None:
    """Test handling of non-string input (shouldn't happen in practice but good to test)."""
    # Type ignore because we're intentionally testing with wrong type
    result = _async_process_target(123)  # type: ignore[arg-type]
    assert result == ("channel_name", 123)  # type: ignore[comparison-overlap]


def test_process_target_strip_multiple_hashes() -> None:
    """Test that multiple # characters are all stripped."""
    assert _async_process_target("###general") == ("channel_name", "general")


async def test_dm_channel_api_error(mock_client) -> None:
    """Test handling of Slack API error when opening DM channel."""
    mock_client.conversations_open.side_effect = SlackApiError("error", {"ok": False})
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    with pytest.raises(HomeAssistantError) as excinfo:
        await service.async_send_message("test", target="U123456789")

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "error_opening_dm"
    assert excinfo.value.translation_placeholders == {
        "error": "error\nThe server responded with: {'ok': False}",
        "user_id": "U123456789",
    }

    mock_client.chat_postMessage.assert_not_called()


async def test_channel_id_cache(mock_client) -> None:
    """Test channel ID is cached and reused."""
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    # First call should use API
    await service.async_send_message("test", target="#general")
    assert mock_client.conversations_list.call_count == 2

    # Second call should use cached value
    await service.async_send_message("test", target="#general")
    assert mock_client.conversations_list.call_count == 2  # Count shouldn't increase


async def test_local_file_upload(mock_client, hass_mock) -> None:
    """Test successful local file upload."""
    hass_mock.config.is_allowed_path = Mock(return_value=True)
    service = SlackNotificationService(hass_mock, mock_client, CONF_DATA)

    with (
        patch("homeassistant.components.slack.notify.DATA_SCHEMA") as mock_schema,
        patch(
            "aiofiles.open",
            return_value=AsyncMock(
                __aenter__=AsyncMock(
                    return_value=AsyncMock(read=AsyncMock(return_value=b"file content"))
                ),
                __aexit__=AsyncMock(),
            ),
        ),
    ):
        mock_schema.side_effect = lambda x: x

        data = {"file": {"path": "/allowed/path/image.jpg"}}

        await service.async_send_message("test", target="#general", data=data)

        mock_client.files_upload_v2.assert_called_once_with(
            channel="C111",
            file=b"file content",
            filename="image.jpg",
            title="image.jpg",
            initial_comment="test",
            thread_ts="",
        )


async def test_local_file_not_allowed(hass_mock, mock_client) -> None:
    """Test uploading a local file that's not in an allowed path."""
    hass_mock.config.is_allowed_path = Mock(return_value=False)
    service = SlackNotificationService(hass_mock, mock_client, CONF_DATA)

    with patch("homeassistant.components.slack.notify.DATA_SCHEMA") as mock_schema:
        mock_schema.side_effect = lambda x: x

        await service.async_send_message(
            "test", target="#general", data={"file": {"path": "/not/allowed/path.jpg"}}
        )

        hass_mock.config.is_allowed_path.assert_called_once_with(
            "/not/allowed/path.jpg"
        )
        mock_client.files_upload_v2.assert_not_called()

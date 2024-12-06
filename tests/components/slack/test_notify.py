"""Test slack notifications."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, Mock

import pytest
from slack_sdk.errors import SlackApiError

from homeassistant.components import notify
from homeassistant.components.slack import DOMAIN
from homeassistant.components.slack.notify import (
    ATTR_THREAD_TS,
    CONF_DEFAULT_CHANNEL,
    DATA_CLIENT,
    SLACK_DATA,
    SlackNotificationService,
    _async_get_filename_from_url,
    async_get_service,
)
from homeassistant.const import ATTR_ICON, CONF_API_KEY, CONF_NAME, CONF_PLATFORM

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


async def test_message_includes_default_emoji() -> None:
    """Tests that default icon is used when no message icon is given."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    expected_icon = ":robot_face:"
    service = SlackNotificationService(
        None, mock_client, CONF_DATA | {ATTR_ICON: expected_icon}
    )

    await service.async_send_message("test")

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_emoji"] == expected_icon


async def test_message_emoji_overrides_default() -> None:
    """Tests that overriding the default icon emoji when sending a message works."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    service = SlackNotificationService(
        None, mock_client, CONF_DATA | {ATTR_ICON: "default_icon"}
    )

    expected_icon = ":new:"
    await service.async_send_message("test", data={"icon": expected_icon})

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_emoji"] == expected_icon


async def test_message_includes_default_icon_url() -> None:
    """Tests that overriding the default icon url when sending a message works."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    expected_icon = "https://example.com/hass.png"
    service = SlackNotificationService(
        None, mock_client, CONF_DATA | {ATTR_ICON: expected_icon}
    )

    await service.async_send_message("test")

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_url"] == expected_icon


async def test_message_icon_url_overrides_default() -> None:
    """Tests that overriding the default icon url when sending a message works."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    service = SlackNotificationService(
        None, mock_client, CONF_DATA | {ATTR_ICON: "default_icon"}
    )

    expected_icon = "https://example.com/hass.png"
    await service.async_send_message("test", data={ATTR_ICON: expected_icon})

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_url"] == expected_icon


async def test_message_as_reply() -> None:
    """Tests that a message pointer will be passed to Slack if specified."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    expected_ts = "1624146685.064129"
    await service.async_send_message("test", data={ATTR_THREAD_TS: expected_ts})

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["thread_ts"] == expected_ts


@pytest.mark.asyncio
async def test_send_local_image() -> None:
    """Tests that sending a local image works."""
    mock_client = Mock()
    mock_client.files_upload_v2 = AsyncMock(
        return_value={"file": {"permalink": "http://example.com/image.png"}}
    )
    mock_client.conversations_list = AsyncMock(
        return_value={"channels": [{"id": "C12345", "name": "general"}]}
    )
    mock_hass = Mock()
    mock_hass.config.is_allowed_path = Mock(return_value=True)
    service = SlackNotificationService(mock_hass, mock_client, CONF_DATA)

    local_image_path = "tests/components/image_upload/logo.png"
    message = "Here is a local image"
    title = "Local Image"
    targets = ["#general"]

    await service._async_send_local_file_message(
        path=local_image_path,
        targets=targets,
        message=message,
        title=title,
        thread_ts=None,
    )

    mock_fn = mock_client.files_upload_v2
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["filename"] == "logo.png"
    assert kwargs["initial_comment"] == message
    assert kwargs["title"] == title
    assert kwargs["channel"] == "C12345"


@pytest.mark.asyncio
async def test_send_local_image_path_not_allowed() -> None:
    """Tests that sending a local image fails if the path is not allowed."""
    mock_client = Mock()
    mock_client.files_upload_v2 = AsyncMock()
    mock_hass = Mock()
    mock_hass.config.is_allowed_path = Mock(return_value=False)
    service = SlackNotificationService(mock_hass, mock_client, CONF_DATA)

    local_image_path = "tests/components/image_upload/logo.png"
    message = "Here is a local image"
    title = "Local Image"
    targets = ["#general"]

    await service._async_send_local_file_message(
        path=local_image_path,
        targets=targets,
        message=message,
        title=title,
        thread_ts=None,
    )

    mock_fn = mock_client.files_upload_v2
    mock_fn.assert_not_called()


@pytest.mark.asyncio
async def test_send_local_image_file_not_exist() -> None:
    """Tests that sending a local image fails if the file does not exist."""
    mock_client = Mock()
    mock_client.files_upload_v2 = AsyncMock()
    mock_hass = Mock()
    mock_hass.config.is_allowed_path = Mock(return_value=True)
    service = SlackNotificationService(mock_hass, mock_client, CONF_DATA)

    local_image_path = "tests/components/image_upload/non_existent_logo.png"
    message = "Here is a local image"
    title = "Local Image"
    targets = ["#general"]

    # Mock os.path.exists to return False
    os.path.exists = Mock(return_value=False)

    await service._async_send_local_file_message(
        path=local_image_path,
        targets=targets,
        message=message,
        title=title,
        thread_ts=None,
    )

    mock_fn = mock_client.files_upload_v2
    mock_fn.assert_not_called()


@pytest.mark.asyncio
async def test_send_local_image_success() -> None:
    """Tests that sending a local image works."""
    mock_client = Mock()
    mock_client.files_upload_v2 = AsyncMock(
        return_value={"file": {"permalink": "http://example.com/image.png"}}
    )
    mock_client.conversations_list = AsyncMock(
        return_value={"channels": [{"id": "C12345", "name": "general"}]}
    )
    mock_hass = Mock()
    mock_hass.config.is_allowed_path = Mock(return_value=True)
    service = SlackNotificationService(mock_hass, mock_client, CONF_DATA)

    local_image_path = "tests/components/image_upload/logo.png"
    message = "Here is a local image"
    title = "Local Image"
    targets = ["#general"]

    # Mock os.path.exists to return True
    os.path.exists = Mock(return_value=True)

    await service._async_send_local_file_message(
        path=local_image_path,
        targets=targets,
        message=message,
        title=title,
        thread_ts=None,
    )

    mock_fn = mock_client.files_upload_v2
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["filename"] == "logo.png"
    assert kwargs["initial_comment"] == message
    assert kwargs["title"] == title
    assert kwargs["channel"] == "C12345"


@pytest.mark.asyncio
async def test_get_channel_id_public_channel() -> None:
    """Tests that the correct channel ID is returned for a public channel."""
    mock_client = Mock()
    mock_client.conversations_list = AsyncMock(
        return_value={"channels": [{"id": "C12345", "name": "general"}]}
    )
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    channel_id = await service._async_get_channel_id("general")

    assert channel_id == "C12345"


@pytest.mark.asyncio
async def test_get_channel_id_private_channel() -> None:
    """Tests that the correct channel ID is returned for a private channel."""
    mock_client = Mock()
    mock_client.conversations_list = AsyncMock(
        return_value={"channels": [{"id": "C67890", "name": "private"}]}
    )
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    channel_id = await service._async_get_channel_id("private")

    assert channel_id == "C67890"


@pytest.mark.asyncio
async def test_get_channel_id_channel_not_found() -> None:
    """Tests that None is returned when the channel is not found."""
    mock_client = Mock()
    mock_client.conversations_list = AsyncMock(
        return_value={"channels": [{"id": "C12345", "name": "general"}]}
    )
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    channel_id = await service._async_get_channel_id("nonexistent")

    assert channel_id is None


@pytest.mark.asyncio
async def test_get_channel_id_slack_api_error() -> None:
    """Tests that None is returned when there is a Slack API error."""
    mock_client = Mock()
    mock_client.conversations_list = AsyncMock(side_effect=SlackApiError("Error", {}))
    service = SlackNotificationService(None, mock_client, CONF_DATA)

    channel_id = await service._async_get_channel_id("general")

    assert channel_id is None


@pytest.mark.asyncio
async def test_async_get_service_with_discovery_info() -> None:
    """Test async_get_service with discovery_info."""
    mock_hass = Mock()
    mock_client = Mock()
    discovery_info = {
        SLACK_DATA: {
            DATA_CLIENT: mock_client,
        }
    }

    service = await async_get_service(mock_hass, {}, discovery_info)

    assert service is not None
    assert isinstance(service, SlackNotificationService)
    assert service._hass == mock_hass
    assert service._client == mock_client
    assert service._config == discovery_info


@pytest.mark.asyncio
async def test_async_get_service_without_discovery_info() -> None:
    """Test async_get_service without discovery_info."""
    mock_hass = Mock()

    service = await async_get_service(mock_hass, {}, None)

    assert service is None


@pytest.mark.parametrize(
    ("url", "expected_filename"),
    [
        ("http://example.com/path/to/file.txt", "file.txt"),
        ("https://example.com/another/path/to/file.jpg", "file.jpg"),
        ("https://example.com/file_without_path", "file_without_path"),
        (
            "https://example.com/path/to/file_with_query.txt?query=123",
            "file_with_query.txt",
        ),
        (
            "https://example.com/path/to/file_with_fragment.txt#fragment",
            "file_with_fragment.txt",
        ),
        (
            "https://example.com/path/to/file_with_query_and_fragment.txt?query=123#fragment",
            "file_with_query_and_fragment.txt",
        ),
    ],
)
def test_async_get_filename_from_url(url, expected_filename) -> None:
    """Test _async_get_filename_from_url with various URLs."""

    assert _async_get_filename_from_url(url) == expected_filename

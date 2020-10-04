"""Test slack notifications"""
from homeassistant.components.slack.notify import SlackNotificationService

from tests.async_mock import AsyncMock


async def test_message_includes_default_emoji():
    """Tests that overriding the default icon emoji when sending a message works."""
    mock_client = AsyncMock()
    expected_icon = ":robot_face:"
    service = SlackNotificationService(None, mock_client, "_", "_", expected_icon)

    await service.async_send_message("test")

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    assert mock_fn.mock_calls[0].kwargs["icon_emoji"] == expected_icon


async def test_message_emoji_overrides_default():
    """Tests that overriding the default icon emoji when sending a message works."""
    mock_client = AsyncMock()
    service = SlackNotificationService(None, mock_client, "_", "_", "default_icon")

    expected_icon = ":new:"
    await service.async_send_message("test", data={"icon": expected_icon})

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    assert mock_fn.mock_calls[0].kwargs["icon_emoji"] == expected_icon


async def test_message_includes_default_icon_url():
    """Tests that overriding the default icon url when sending a message works."""
    mock_client = AsyncMock()
    expected_icon = "https://example.com/hass.png"
    service = SlackNotificationService(None, mock_client, "_", "_", expected_icon)

    await service.async_send_message("test")

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    assert mock_fn.mock_calls[0].kwargs["icon_url"] == expected_icon


async def test_message_icon_url_overrides_default():
    """Tests that overriding the default icon url when sending a message works."""
    mock_client = AsyncMock()
    service = SlackNotificationService(None, mock_client, "_", "_", "default_icon")

    expected_icon = "https://example.com/hass.png"
    await service.async_send_message("test", data={"icon": expected_icon})

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    assert mock_fn.mock_calls[0].kwargs["icon_url"] == expected_icon

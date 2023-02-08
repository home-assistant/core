"""Test slack notifications."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from homeassistant.components import notify
from homeassistant.components.slack import DOMAIN
from homeassistant.components.slack.notify import (
    CONF_DEFAULT_CHANNEL,
    SlackNotificationService,
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

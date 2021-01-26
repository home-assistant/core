"""Test slack notifications."""
import logging
from unittest.mock import AsyncMock, Mock, patch

from _pytest.logging import LogCaptureFixture
import aiohttp
from slack.errors import SlackApiError

from homeassistant.components.slack.notify import (
    CONF_DEFAULT_CHANNEL,
    SlackNotificationService,
    async_get_service,
)
from homeassistant.const import CONF_API_KEY, CONF_ICON, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

MODULE_PATH = "homeassistant.components.slack.notify"


async def test_get_service(hass: HomeAssistantType, caplog: LogCaptureFixture):
    """Test async_get_service with exceptions."""
    config = {
        CONF_API_KEY: "12345",
        CONF_DEFAULT_CHANNEL: "channel",
    }

    with patch(MODULE_PATH + ".aiohttp_client") as mock_session, patch(
        MODULE_PATH + ".WebClient"
    ) as mock_client, patch(
        MODULE_PATH + ".SlackNotificationService"
    ) as mock_slack_service:
        mock_session.async_get_clientsession.return_value = session = Mock()
        mock_client.return_value = client = AsyncMock()

        # Normal setup
        mock_slack_service.return_value = service = Mock()
        assert await async_get_service(hass, config) == service
        mock_slack_service.assert_called_once_with(
            hass, client, "channel", username=None, icon=None
        )
        mock_client.assert_called_with(token="12345", run_async=True, session=session)
        client.auth_test.assert_called_once_with()
        mock_slack_service.assert_called_once_with(
            hass, client, "channel", username=None, icon=None
        )
        mock_slack_service.reset_mock()

        # aiohttp.ClientError
        config.update({CONF_USERNAME: "user", CONF_ICON: "icon"})
        mock_slack_service.reset_mock()
        mock_slack_service.return_value = service = Mock()
        client.auth_test.side_effect = [aiohttp.ClientError]
        assert await async_get_service(hass, config) == service
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.WARNING
        assert aiohttp.ClientError.__qualname__ in record.message
        caplog.records.clear()
        mock_slack_service.assert_called_once_with(
            hass, client, "channel", username="user", icon="icon"
        )
        mock_slack_service.reset_mock()

        # SlackApiError
        err, level = SlackApiError("msg", "resp"), logging.ERROR
        client.auth_test.side_effect = [err]
        assert await async_get_service(hass, config) is None
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == level
        assert err.__class__.__qualname__ in record.message
        caplog.records.clear()
        mock_slack_service.assert_not_called()
        mock_slack_service.reset_mock()


async def test_message_includes_default_emoji():
    """Tests that default icon is used when no message icon is given."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    expected_icon = ":robot_face:"
    service = SlackNotificationService(None, mock_client, "_", "_", expected_icon)

    await service.async_send_message("test")

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_emoji"] == expected_icon


async def test_message_emoji_overrides_default():
    """Tests that overriding the default icon emoji when sending a message works."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    service = SlackNotificationService(None, mock_client, "_", "_", "default_icon")

    expected_icon = ":new:"
    await service.async_send_message("test", data={"icon": expected_icon})

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_emoji"] == expected_icon


async def test_message_includes_default_icon_url():
    """Tests that overriding the default icon url when sending a message works."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    expected_icon = "https://example.com/hass.png"
    service = SlackNotificationService(None, mock_client, "_", "_", expected_icon)

    await service.async_send_message("test")

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_url"] == expected_icon


async def test_message_icon_url_overrides_default():
    """Tests that overriding the default icon url when sending a message works."""
    mock_client = Mock()
    mock_client.chat_postMessage = AsyncMock()
    service = SlackNotificationService(None, mock_client, "_", "_", "default_icon")

    expected_icon = "https://example.com/hass.png"
    await service.async_send_message("test", data={"icon": expected_icon})

    mock_fn = mock_client.chat_postMessage
    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["icon_url"] == expected_icon

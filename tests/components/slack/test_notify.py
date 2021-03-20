"""Test slack notifications."""
from __future__ import annotations

import copy
import logging
from unittest.mock import AsyncMock, Mock, patch

from _pytest.logging import LogCaptureFixture
import aiohttp
from slack.errors import SlackApiError

from homeassistant.components import notify
from homeassistant.components.slack import DOMAIN
from homeassistant.components.slack.notify import (
    CONF_DEFAULT_CHANNEL,
    SlackNotificationService,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ICON,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

MODULE_PATH = "homeassistant.components.slack.notify"
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


def filter_log_records(caplog: LogCaptureFixture) -> list[logging.LogRecord]:
    """Filter all unrelated log records."""
    return [
        rec for rec in caplog.records if rec.name.endswith(f"{DOMAIN}.{notify.DOMAIN}")
    ]


async def test_setup(hass: HomeAssistantType, caplog: LogCaptureFixture):
    """Test setup slack notify."""
    config = DEFAULT_CONFIG

    with patch(
        MODULE_PATH + ".aiohttp_client",
        **{"async_get_clientsession.return_value": (session := Mock())},
    ), patch(
        MODULE_PATH + ".WebClient",
        return_value=(client := AsyncMock()),
    ) as mock_client:

        await async_setup_component(hass, notify.DOMAIN, config)
        await hass.async_block_till_done()
        assert hass.services.has_service(notify.DOMAIN, SERVICE_NAME)
        caplog_records_slack = filter_log_records(caplog)
        assert len(caplog_records_slack) == 0
        mock_client.assert_called_with(token="12345", run_async=True, session=session)
        client.auth_test.assert_called_once_with()


async def test_setup_clientError(hass: HomeAssistantType, caplog: LogCaptureFixture):
    """Test setup slack notify with aiohttp.ClientError exception."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config[notify.DOMAIN][0].update({CONF_USERNAME: "user", CONF_ICON: "icon"})

    with patch(
        MODULE_PATH + ".aiohttp_client",
        **{"async_get_clientsession.return_value": Mock()},
    ), patch(MODULE_PATH + ".WebClient", return_value=(client := AsyncMock())):

        client.auth_test.side_effect = [aiohttp.ClientError]
        await async_setup_component(hass, notify.DOMAIN, config)
        await hass.async_block_till_done()
        assert hass.services.has_service(notify.DOMAIN, SERVICE_NAME)
        caplog_records_slack = filter_log_records(caplog)
        assert len(caplog_records_slack) == 1
        record = caplog_records_slack[0]
        assert record.levelno == logging.WARNING
        assert aiohttp.ClientError.__qualname__ in record.message


async def test_setup_slackApiError(hass: HomeAssistantType, caplog: LogCaptureFixture):
    """Test setup slack notify with SlackApiError exception."""
    config = DEFAULT_CONFIG

    with patch(
        MODULE_PATH + ".aiohttp_client",
        **{"async_get_clientsession.return_value": Mock()},
    ), patch(MODULE_PATH + ".WebClient", return_value=(client := AsyncMock())):

        client.auth_test.side_effect = [err := SlackApiError("msg", "resp")]
        await async_setup_component(hass, notify.DOMAIN, config)
        await hass.async_block_till_done()
        assert hass.services.has_service(notify.DOMAIN, SERVICE_NAME) is False
        caplog_records_slack = filter_log_records(caplog)
        assert len(caplog_records_slack) == 1
        record = caplog_records_slack[0]
        assert record.levelno == logging.ERROR
        assert err.__class__.__qualname__ in record.message


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

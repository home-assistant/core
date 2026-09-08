"""Test slack notifications."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components import notify
from homeassistant.components.slack import DOMAIN
from homeassistant.components.slack.notify import ATTR_THREAD_TS
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import CONF_DATA, TEAM_ID, mock_connection

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

SERVICE_NAME = "test_team"


async def _async_setup_notify_service(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entry_data: dict[str, str],
) -> AsyncMock:
    """Set up the slack integration and mock the message client."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=TEAM_ID)
    entry.add_to_hass(hass)
    mock_connection(aioclient_mock)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(notify.DOMAIN, SERVICE_NAME)
    mock_fn = AsyncMock()
    entry.runtime_data.client.chat_postMessage = mock_fn
    return mock_fn


@pytest.mark.parametrize(
    ("entry_icon", "service_data", "expected_key", "expected_icon"),
    [
        pytest.param(
            ":robot_face:",
            {notify.ATTR_MESSAGE: "test"},
            "icon_emoji",
            ":robot_face:",
            id="default_emoji",
        ),
        pytest.param(
            "default_icon",
            {notify.ATTR_MESSAGE: "test", notify.ATTR_DATA: {ATTR_ICON: ":new:"}},
            "icon_emoji",
            ":new:",
            id="emoji_overrides_default",
        ),
        pytest.param(
            "https://example.com/hass.png",
            {notify.ATTR_MESSAGE: "test"},
            "icon_url",
            "https://example.com/hass.png",
            id="default_icon_url",
        ),
        pytest.param(
            "default_icon",
            {
                notify.ATTR_MESSAGE: "test",
                notify.ATTR_DATA: {ATTR_ICON: "https://example.com/hass.png"},
            },
            "icon_url",
            "https://example.com/hass.png",
            id="icon_url_overrides_default",
        ),
    ],
)
async def test_message_icon(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entry_icon: str,
    service_data: dict[str, str],
    expected_key: str,
    expected_icon: str,
) -> None:
    """Test that the message icon comes from the entry data or the service data."""
    mock_fn = await _async_setup_notify_service(
        hass, aioclient_mock, CONF_DATA | {ATTR_ICON: entry_icon}
    )

    await hass.services.async_call(
        notify.DOMAIN, SERVICE_NAME, service_data, blocking=True
    )

    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs[expected_key] == expected_icon


async def test_message_as_reply(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Tests that a message pointer will be passed to Slack if specified."""
    mock_fn = await _async_setup_notify_service(hass, aioclient_mock, CONF_DATA)

    expected_ts = "1624146685.064129"
    await hass.services.async_call(
        notify.DOMAIN,
        SERVICE_NAME,
        {
            notify.ATTR_MESSAGE: "test",
            notify.ATTR_DATA: {ATTR_THREAD_TS: expected_ts},
        },
        blocking=True,
    )

    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs["thread_ts"] == expected_ts


async def test_invalid_message_data(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Tests that invalid message data raises an error and sends no message."""
    mock_fn = await _async_setup_notify_service(hass, aioclient_mock, CONF_DATA)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            notify.DOMAIN,
            SERVICE_NAME,
            {
                notify.ATTR_MESSAGE: "test",
                notify.ATTR_DATA: {"not_a_valid_key": "value"},
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_message_data"
    mock_fn.assert_not_called()

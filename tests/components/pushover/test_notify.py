"""Test the pushover notify platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.pushover import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture(autouse=False)
def mock_pushover():
    """Mock pushover."""
    with patch(
        "pushover_complete.PushoverAPI._generic_post", return_value={}
    ) as mock_generic_post:
        yield mock_generic_post


@pytest.fixture
def mock_send_message():
    """Patch PushoverAPI.send_message for TTL test."""
    with patch(
        "homeassistant.components.pushover.notify.PushoverAPI.send_message"
    ) as mock:
        yield mock


async def test_send_message(
    hass: HomeAssistant, mock_pushover: MagicMock, mock_send_message: MagicMock
) -> None:
    """Test sending a message."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "pushover",
            "api_key": "API_KEY",
            "user_key": "USER_KEY",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "notify",
        "pushover",
        {"message": "Hello TTL", "data": {"ttl": 900}},
        blocking=True,
    )

    mock_send_message.assert_called_once_with(
        user="USER_KEY",
        message="Hello TTL",
        device="",
        title="Home Assistant",
        url=None,
        url_title=None,
        image=None,
        priority=None,
        retry=None,
        expire=None,
        callback_url=None,
        timestamp=None,
        sound=None,
        html=0,
        ttl=900,
    )


@pytest.mark.usefixtures("mock_pushover")
@pytest.mark.parametrize(
    ("is_allowed", "translation_key"),
    [
        pytest.param(False, "attachment_not_allowed", id="not_allowed"),
        pytest.param(True, "attachment_open_failed", id="open_failed"),
    ],
)
async def test_send_message_attachment_error(
    hass: HomeAssistant,
    mock_send_message: MagicMock,
    is_allowed: bool,
    translation_key: str,
) -> None:
    """Test that an unusable attachment raises and sends nothing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "name": "pushover",
            "api_key": "API_KEY",
            "user_key": "USER_KEY",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch.object(hass.config, "is_allowed_path", return_value=is_allowed),
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            "notify",
            "pushover",
            {
                "message": "Hello",
                "data": {"attachment": "/nonexistent/attachment.jpg"},
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    mock_send_message.assert_not_called()

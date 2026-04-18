"""Test the pushover notify platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.pushover import DOMAIN
from homeassistant.core import HomeAssistant

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

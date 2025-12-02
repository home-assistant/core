"""Test the pushover notify platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.pushover import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

RECEIPT = "1758472711"


@pytest.fixture(autouse=False)
def mock_pushover():
    """Mock pushover."""
    with patch("pushover_complete.PushoverAPI._generic_post") as mock_generic_post:
        yield mock_generic_post


@pytest.fixture
def mock_send_message():
    """Patch PushoverAPI.send_message for TTL test."""
    with patch(
        "homeassistant.components.pushover.notify.PushoverAPI.send_message",
    ) as mock:
        yield mock


@pytest.fixture
def mock_send_message_prio2():
    """Patch PushoverAPI.send_message for cancel test."""
    with patch(
        "homeassistant.components.pushover.notify.PushoverAPI.send_message",
        return_value={"receipt": RECEIPT},
    ) as mock:
        yield mock


@pytest.fixture
def mock_cancel_receipt():
    """Patch PushoverAPI.cancel_receipt for cancel test."""
    with patch(
        "homeassistant.components.pushover.notify.PushoverAPI.cancel_receipt"
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


async def test_cancel_message(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
    mock_send_message_prio2: MagicMock,
    mock_cancel_receipt: MagicMock,
) -> None:
    """Test cancelling a message."""
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
        {
            "message": "Hello Emergency",
            "data": {"ttl": 900, "priority": 2, "retry": 30, "tags": "tag1"},
        },
        blocking=True,
    )

    mock_send_message_prio2.assert_called_once_with(
        user="USER_KEY",
        message="Hello Emergency",
        device="",
        title="Home Assistant",
        url=None,
        url_title=None,
        image=None,
        priority=2,
        retry=30,
        expire=None,
        callback_url=None,
        timestamp=None,
        sound=None,
        html=0,
        ttl=900,
    )

    await hass.services.async_call(
        "pushover",
        "cancel",
        {"tag": "tag1"},
        blocking=True,
    )

    mock_cancel_receipt.assert_called_once_with(RECEIPT)

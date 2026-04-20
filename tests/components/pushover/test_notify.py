"""Test the pushover notify platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.pushover import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG

from tests.common import MockConfigEntry

RECEIPT_A = "receipt_aaa111"
RECEIPT_B = "receipt_bbb222"
TAG_ALARM = "alarm"


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


@pytest.fixture
def mock_send_message_prio2():
    """Patch PushoverAPI.send_message returning a receipt for emergency messages."""
    with patch(
        "homeassistant.components.pushover.notify.PushoverAPI.send_message",
        return_value={"receipt": RECEIPT_A},
    ) as mock:
        yield mock


@pytest.fixture
def mock_cancel_receipt():
    """Patch PushoverAPI.cancel_receipt."""
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
        data=MOCK_CONFIG,
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
        user="MYUSERKEY",
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


async def test_cancel_by_tag(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
    mock_send_message_prio2: MagicMock,
    mock_cancel_receipt: MagicMock,
) -> None:
    """Test cancelling an emergency message by tag."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "notify",
        "pushover",
        {
            "message": "Emergency!",
            "data": {"priority": 2, "retry": 30, "expire": 3600, "tags": TAG_ALARM},
        },
        blocking=True,
    )

    await hass.services.async_call(
        DOMAIN,
        "cancel",
        {"tag": TAG_ALARM},
        blocking=True,
    )

    mock_cancel_receipt.assert_called_once_with(RECEIPT_A)
    assert hass.data[DOMAIN]["services"][entry.entry_id]._receipt_tags == {}


async def test_cancel_all(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
    mock_send_message_prio2: MagicMock,
    mock_cancel_receipt: MagicMock,
) -> None:
    """Test cancelling all emergency messages when no tag is supplied."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "notify",
        "pushover",
        {
            "message": "Emergency!",
            "data": {"priority": 2, "retry": 30, "expire": 3600, "tags": TAG_ALARM},
        },
        blocking=True,
    )

    await hass.services.async_call(DOMAIN, "cancel", {}, blocking=True)

    mock_cancel_receipt.assert_called_once_with(RECEIPT_A)
    assert hass.data[DOMAIN]["services"][entry.entry_id]._receipt_tags == {}


async def test_cancel_unloads_service_with_last_entry(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
    mock_send_message: MagicMock,
) -> None:
    """Test that the cancel service is removed when the last entry is unloaded."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "cancel")

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "cancel")


async def test_cancel_multiple_receipts_same_tag(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
    mock_cancel_receipt: MagicMock,
) -> None:
    """Test that multiple emergency messages with the same tag are all cancelled."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.pushover.notify.PushoverAPI.send_message",
        side_effect=[{"receipt": RECEIPT_A}, {"receipt": RECEIPT_B}],
    ):
        await hass.services.async_call(
            "notify",
            "pushover",
            {
                "message": "First",
                "data": {"priority": 2, "retry": 30, "tags": TAG_ALARM},
            },
            blocking=True,
        )
        await hass.services.async_call(
            "notify",
            "pushover",
            {
                "message": "Second",
                "data": {"priority": 2, "retry": 30, "tags": TAG_ALARM},
            },
            blocking=True,
        )

    await hass.services.async_call(DOMAIN, "cancel", {"tag": TAG_ALARM}, blocking=True)

    assert mock_cancel_receipt.call_count == 2
    called_receipts = {c.args[0] for c in mock_cancel_receipt.call_args_list}
    assert called_receipts == {RECEIPT_A, RECEIPT_B}

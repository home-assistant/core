"""Test the pushover notify platform."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from pushover_complete import BadAPIRequestError
import pytest

from homeassistant.components.pushover import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

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
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
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


@pytest.mark.usefixtures("mock_pushover")
async def test_send_message_with_attachment(
    hass: HomeAssistant,
    mock_send_message: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that a readable attachment is sent as an open file."""
    attachment = tmp_path / "attachment.jpg"
    attachment.write_bytes(b"image data")

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await hass.services.async_call(
            "notify",
            "pushover",
            {
                "message": "Hello",
                "data": {"attachment": str(attachment)},
            },
            blocking=True,
        )

    image = mock_send_message.call_args.kwargs["image"]
    assert image.name == str(attachment)
    image.close()


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
        {"entry_id": entry.entry_id, "tag": TAG_ALARM},
        blocking=True,
    )

    mock_cancel_receipt.assert_called_once_with(RECEIPT_A)
    assert entry.runtime_data.notify_service._receipt_tags == {}


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

    await hass.services.async_call(
        DOMAIN, "cancel", {"entry_id": entry.entry_id}, blocking=True
    )

    mock_cancel_receipt.assert_called_once_with(RECEIPT_A)
    assert entry.runtime_data.notify_service._receipt_tags == {}


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
                "data": {"priority": 2, "retry": 30, "expire": 3600, "tags": TAG_ALARM},
            },
            blocking=True,
        )
        await hass.services.async_call(
            "notify",
            "pushover",
            {
                "message": "Second",
                "data": {"priority": 2, "retry": 30, "expire": 3600, "tags": TAG_ALARM},
            },
            blocking=True,
        )

    await hass.services.async_call(
        DOMAIN,
        "cancel",
        {"entry_id": entry.entry_id, "tag": TAG_ALARM},
        blocking=True,
    )

    assert mock_cancel_receipt.call_count == 2
    called_receipts = {c.args[0] for c in mock_cancel_receipt.call_args_list}
    assert called_receipts == {RECEIPT_A, RECEIPT_B}


async def test_cancel_unknown_entry_id(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
) -> None:
    """Test cancel with an entry_id that does not exist."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "cancel", {"entry_id": "nonexistent"}, blocking=True
        )


async def test_cancel_empty_receipt_tags(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
    mock_send_message: MagicMock,
    mock_cancel_receipt: MagicMock,
) -> None:
    """Test cancel when no receipts have been stored."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "cancel",
        {"entry_id": entry.entry_id, "tag": TAG_ALARM},
        blocking=True,
    )

    mock_cancel_receipt.assert_not_called()


async def test_cancel_tag_not_found(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
    mock_send_message_prio2: MagicMock,
    mock_cancel_receipt: MagicMock,
) -> None:
    """Test cancel when no receipts match the given tag."""
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
        {"entry_id": entry.entry_id, "tag": "nonexistent"},
        blocking=True,
    )

    mock_cancel_receipt.assert_not_called()


async def test_cancel_receipt_api_error(
    hass: HomeAssistant,
    mock_pushover: MagicMock,
    mock_send_message_prio2: MagicMock,
    mock_cancel_receipt: MagicMock,
) -> None:
    """Test that a BadAPIRequestError during cancel is logged and does not raise."""
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

    mock_cancel_receipt.side_effect = BadAPIRequestError("cancel failed")

    await hass.services.async_call(
        DOMAIN,
        "cancel",
        {"entry_id": entry.entry_id, "tag": TAG_ALARM},
        blocking=True,
    )

    mock_cancel_receipt.assert_called_once_with(RECEIPT_A)
    assert entry.runtime_data.notify_service._receipt_tags == {}

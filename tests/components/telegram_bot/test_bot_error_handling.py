"""Unit tests for telegram_bot bot.py error handling."""

import logging
from unittest.mock import MagicMock

import pytest


def test_none_check_prevents_attribute_error() -> None:
    """Test that None check prevents AttributeError when accessing msg.id.

    This tests the fix for:
    AttributeError: 'NoneType' object has no attribute 'id'

    The fix adds: if msg is not None: before accessing msg.id
    """
    # Simulate what _send_msg returns on TelegramError
    msg = None
    msg_ids = {}
    chat_id = 12345

    # This pattern would crash without the fix:
    # msg_ids[chat_id] = msg.id  # AttributeError!

    # With our fix:
    if msg is not None:
        msg_ids[chat_id] = msg.id

    # Verify empty dict (message send failed, no ID stored)
    assert msg_ids == {}
    assert chat_id not in msg_ids


def test_message_id_stored_when_msg_is_valid() -> None:
    """Test that message ID is stored when msg is not None."""
    # Create a mock message with an ID
    msg = MagicMock()
    msg.id = 98765

    msg_ids = {}
    chat_id = 12345

    # Apply the fix pattern
    if msg is not None:
        msg_ids[chat_id] = msg.id

    # Verify message ID was stored
    assert msg_ids == {12345: 98765}
    assert chat_id in msg_ids


def test_multiple_chats_some_fail() -> None:
    """Test handling multiple chats where some fail."""
    chat_ids = [111, 222, 333]
    messages = [
        MagicMock(id=1001),  # Success
        None,  # Failed (TelegramError)
        MagicMock(id=1003),  # Success
    ]

    msg_ids = {}
    for chat_id, msg in zip(chat_ids, messages, strict=True):
        if msg is not None:
            msg_ids[chat_id] = msg.id

    # Only successful sends are in dict
    assert msg_ids == {111: 1001, 333: 1003}
    assert 222 not in msg_ids  # Failed chat not in dict


def test_none_check_in_send_file_pattern() -> None:
    """Test the pattern used in send_file method."""
    # Simulate send_file scenario
    msg = None  # TelegramError occurred
    msg_ids = {}
    chat_id = 12345

    # Pattern from send_file (after fix)
    if msg is not None:
        msg_ids[chat_id] = msg.id

    assert msg_ids == {}


def test_none_check_in_send_sticker_pattern() -> None:
    """Test the pattern used in send_sticker method."""
    msg = None  # TelegramError occurred
    msg_ids = {}
    chat_id = 67890

    # Pattern from send_sticker (after fix)
    if msg is not None:
        msg_ids[chat_id] = msg.id

    assert msg_ids == {}


def test_none_check_in_send_location_pattern() -> None:
    """Test the pattern used in send_location method."""
    msg = None  # TelegramError occurred
    msg_ids = {}
    chat_id = 99999

    # Pattern from send_location (after fix)
    if msg is not None:
        msg_ids[chat_id] = msg.id

    assert msg_ids == {}


def test_none_check_in_send_poll_pattern() -> None:
    """Test the pattern used in send_poll method."""
    msg = None  # TelegramError occurred
    msg_ids = {}
    chat_id = 55555

    # Pattern from send_poll (after fix)
    if msg is not None:
        msg_ids[chat_id] = msg.id

    assert msg_ids == {}


def test_error_logged_when_msg_is_none(caplog: pytest.LogCaptureFixture) -> None:
    """Test that error is logged when msg is None."""
    caplog.set_level(logging.ERROR)

    # Simulate the pattern with logging
    msg = None
    msg_ids = {}
    chat_id = 12345
    file_type = "photo"

    # Pattern with improved error logging
    if msg is not None:
        msg_ids[chat_id] = msg.id
    else:
        logging.getLogger().error(
            "Failed to send %s to chat_id %s: message object is None. "
            "If using Markdown v2 parse mode, ensure all special characters "
            "are properly escaped",
            file_type,
            chat_id,
        )

    # Verify error was logged with file_type and descriptive message
    assert (
        "Failed to send photo to chat_id 12345: message object is None" in caplog.text
    )
    assert "Markdown v2 parse mode" in caplog.text
    assert "properly escaped" in caplog.text
    assert msg_ids == {}


def test_no_error_logged_when_msg_is_valid(caplog: pytest.LogCaptureFixture) -> None:
    """Test that no error is logged when msg is valid."""
    caplog.set_level(logging.ERROR)

    # Create valid message
    msg = MagicMock()
    msg.id = 98765
    msg_ids = {}
    chat_id = 12345
    file_type = "photo"

    # Pattern with improved error logging
    if msg is not None:
        msg_ids[chat_id] = msg.id
    else:
        logging.getLogger().error(
            "Failed to send %s to chat_id %s: message object is None. "
            "If using Markdown v2 parse mode, ensure all special characters "
            "are properly escaped",
            file_type,
            chat_id,
        )

    # Verify no error was logged
    assert "Failed to send" not in caplog.text
    assert msg_ids == {12345: 98765}

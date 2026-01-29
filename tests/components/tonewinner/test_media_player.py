"""Test for Tonewinner AT-500 media player protocol parsing."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.tonewinner.media_player import TonewinnerProtocol


@pytest.fixture
def mock_entity():
    """Create a mock entity for testing."""
    entity = MagicMock()
    entity.handle_response = MagicMock()
    return entity


@pytest.fixture
def protocol(mock_entity):
    """Create a protocol instance for testing."""
    return TonewinnerProtocol(mock_entity)


def test_single_complete_message(protocol, mock_entity) -> None:
    """Test parsing a single complete message."""
    # Send: #POWER ON*
    protocol.data_received(b"#POWER ON*")

    # Should call handle_response with content between # and *
    mock_entity.handle_response.assert_called_once_with("POWER ON")


def test_multiple_messages_one_chunk(protocol, mock_entity) -> None:
    """Test parsing multiple messages in a single data chunk."""
    # Send: #POWER ON*#VOL 50.1*#SI 09 Sonos V=NO A=CO1*
    protocol.data_received(b"#POWER ON*#VOL 50.1*#SI 09 Sonos V=NO A=CO1*")

    # Should call handle_response for each message
    assert mock_entity.handle_response.call_count == 3
    calls = mock_entity.handle_response.call_args_list

    assert calls[0][0][0] == "POWER ON"
    assert calls[1][0][0] == "VOL 50.1"
    assert calls[2][0][0] == "SI 09 Sonos V=NO A=CO1"


def test_split_message_two_chunks(protocol, mock_entity) -> None:
    """Test parsing a message split across two data chunks."""
    # First chunk: #POWER O
    protocol.data_received(b"#POWER O")

    # Should not have called handle_response yet
    mock_entity.handle_response.assert_not_called()

    # Second chunk: N*#VOLUME=50*
    protocol.data_received(b"N*#VOL 50.1*")

    # Should now have both messages
    assert mock_entity.handle_response.call_count == 2
    calls = mock_entity.handle_response.call_args_list

    assert calls[0][0][0] == "POWER ON"
    assert calls[1][0][0] == "VOL 50.1"


def test_message_with_garbage_before(protocol, mock_entity) -> None:
    """Test parsing when there's garbage data before the message."""
    # Send garbage followed by a valid message
    protocol.data_received(b"junk\x00\xff#POWER ON*")

    # Should ignore garbage and parse the valid message
    mock_entity.handle_response.assert_called_once_with("POWER ON")


def test_garbage_between_messages(protocol, mock_entity) -> None:
    """Test parsing with garbage between valid messages."""
    protocol.data_received(b"#POWER ON*\xff\x00junk#VOL 50.1*")

    assert mock_entity.handle_response.call_count == 2
    calls = mock_entity.handle_response.call_args_list

    assert calls[0][0][0] == "POWER ON"
    assert calls[1][0][0] == "VOL 50.1"


def test_incomplete_message_no_asterisk(protocol, mock_entity) -> None:
    """Test that incomplete messages (no *) are buffered."""
    # Send message without closing *
    protocol.data_received(b"#POWER ON")

    # Should not have called handle_response yet
    mock_entity.handle_response.assert_not_called()

    # Now complete it
    protocol.data_received(b"*#NEXT MSG*")

    # Should now have both messages
    assert mock_entity.handle_response.call_count == 2
    calls = mock_entity.handle_response.call_args_list

    assert calls[0][0][0] == "POWER ON"
    assert calls[1][0][0] == "NEXT MSG"


def test_empty_message_content(protocol, mock_entity) -> None:
    """Test that empty messages (just #*) are ignored."""
    protocol.data_received(b"#*")

    # Should not call handle_response for empty message
    mock_entity.handle_response.assert_not_called()


def test_multiple_empty_messages(protocol, mock_entity) -> None:
    """Test multiple empty and valid messages."""
    protocol.data_received(b"#*#POWER ON*##*#VOL 50.5*#*")

    # ##* has content "#" which is non-empty
    assert mock_entity.handle_response.call_count == 3
    calls = mock_entity.handle_response.call_args_list

    assert calls[0][0][0] == "POWER ON"
    assert calls[1][0][0] == "#"
    assert calls[2][0][0] == "VOL 50.5"


def test_multiple_start_markers(protocol, mock_entity) -> None:
    """Test behavior when multiple # markers appear before *."""
    # This should parse from the last # to the first *
    protocol.data_received(b"##POWER ON*")

    mock_entity.handle_response.assert_called_once()
    # The parser should handle this gracefully - content starts at last #
    assert mock_entity.handle_response.call_args[0][0] == "#POWER ON"


def test_message_with_special_characters(protocol, mock_entity) -> None:
    """Test parsing messages with special characters in content."""
    protocol.data_received(b"#SI 06 eARC/ARC V=NO A=ARC*")

    mock_entity.handle_response.assert_called_once_with("SI 06 eARC/ARC V=NO A=ARC")


def test_binary_data_in_message(protocol, mock_entity) -> None:
    """Test parsing messages with binary data (non-ASCII)."""
    protocol.data_received(b"#DATA=\x01\x02\x03*")

    # Should decode with errors='ignore' as per the code
    mock_entity.handle_response.assert_called_once()


def test_consecutive_chunks_split_messages(protocol, mock_entity) -> None:
    """Test multiple messages split across many chunks."""
    # Message 1 split
    protocol.data_received(b"#POW")
    protocol.data_received(b"ER ON*")

    # Message 2 split across 3 chunks
    protocol.data_received(b"#VOL")
    protocol.data_received(b" ")
    protocol.data_received(b"50.5*")

    # Message 3 complete in one chunk
    protocol.data_received(b"#SI 01 HDMI 2 V= HD2 A=HDMI*")

    assert mock_entity.handle_response.call_count == 3
    calls = mock_entity.handle_response.call_args_list

    assert calls[0][0][0] == "POWER ON"
    assert calls[1][0][0] == "VOL 50.5"
    assert calls[2][0][0] == "SI 01 HDMI 2 V= HD2 A=HDMI"


def test_no_start_marker(protocol, mock_entity) -> None:
    """Test data with no # marker at all."""
    protocol.data_received(b"junk data * more junk")

    # Should not call handle_response - no message found
    mock_entity.handle_response.assert_not_called()

    # Buffer should be empty
    assert protocol.buffer == b""


def test_partial_start_marker(protocol, mock_entity) -> None:
    """Test data that looks like a message but has no *."""
    protocol.data_received(b"#POWER ON")

    # Should buffer it, waiting for *
    mock_entity.handle_response.assert_not_called()
    assert protocol.buffer == b"#POWER ON"

    # Send more data but still no *
    protocol.data_received(b" and more")

    # Still should not call handle_response
    mock_entity.handle_response.assert_not_called()

    # Finally send the terminator
    protocol.data_received(b"*")

    # Now should parse the message
    mock_entity.handle_response.assert_called_once()
    assert mock_entity.handle_response.call_args[0][0] == "POWER ON and more"


def test_back_to_back_messages(protocol, mock_entity) -> None:
    """Test parsing messages with no delimiters between them."""
    protocol.data_received(b"#MSG1*#MSG2*#MSG3*")

    assert mock_entity.handle_response.call_count == 3
    calls = mock_entity.handle_response.call_args_list

    assert calls[0][0][0] == "MSG1"
    assert calls[1][0][0] == "MSG2"
    assert calls[2][0][0] == "MSG3"


def test_long_message(protocol, mock_entity) -> None:
    """Test parsing a very long message."""
    long_content = "DATA=" + "X" * 1000
    protocol.data_received(f"#{long_content}*".encode())

    mock_entity.handle_response.assert_called_once()
    assert mock_entity.handle_response.call_args[0][0] == long_content


def test_buffer_cleared_after_invalid_data(protocol, mock_entity) -> None:
    """Test that buffer is cleared when there's data before any #."""
    # Send data before any #
    protocol.data_received(b"garbage\x00\xff")

    # Buffer should be empty
    assert protocol.buffer == b""

    # Now send a valid message
    protocol.data_received(b"#VALID*")

    # Should parse correctly
    mock_entity.handle_response.assert_called_once_with("VALID")

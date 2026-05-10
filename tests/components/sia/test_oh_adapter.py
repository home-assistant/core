"""Tests for the SIA OH adapter (OHEvent → SIAEvent conversion)."""

from __future__ import annotations

from datetime import datetime

from osbornehoffman import MessageType, OHEvent
from pysiaalarm.utils import SIA_CODES, MessageTypes

from homeassistant.components.sia.oh_adapter import oh_event_to_sia_event
from homeassistant.components.sia.utils import get_event_data_from_sia_event


def _make_oh_event(**overrides) -> OHEvent:
    """Create an OHEvent with sensible defaults."""
    defaults = {
        "peername": ("192.168.1.100", 5000),
        "message_type": MessageType.SIA,
        "system_account": "AABBCC",
        "account": "112233",
        "receiver": "0001",
        "line": "0001",
        "sequence": "1234",
        "sia_event": "BA",
        "sia_zone": "01",
        "text": "Burglary Alarm Zone 1",
        "panel_id": 42,
        "timestamp": datetime(2025, 6, 15, 12, 30, 0),
    }
    defaults.update(overrides)
    return OHEvent(**defaults)


def test_sia_message_type_mapping() -> None:
    """Test SIA event maps to MessageTypes.SIADCS."""
    event = _make_oh_event(message_type=MessageType.SIA)
    sia = oh_event_to_sia_event(event)
    assert sia.message_type == MessageTypes.SIADCS


def test_cid_message_type_mapping() -> None:
    """Test CID event maps to MessageTypes.ADMCID."""
    event = _make_oh_event(
        message_type=MessageType.CID,
        qualifier="1",
        event_code="130",
        area="01",
        sia_event=None,
    )
    sia = oh_event_to_sia_event(event)
    assert sia.message_type == MessageTypes.ADMCID
    assert sia.event_qualifier == "1"
    assert sia.event_type == "130"
    assert sia.partition == "01"


def test_heartbeat_mapping() -> None:
    """Test heartbeat event maps to MessageTypes.NULL with code RP."""
    event = _make_oh_event(
        message_type=MessageType.HB_V1,
        sia_event=None,
    )
    sia = oh_event_to_sia_event(event)
    assert sia.message_type == MessageTypes.NULL
    # OHEvent.code property returns "RP" for heartbeats
    assert sia.code == "RP"


def test_hb_v2_mapping() -> None:
    """Test HB_V2 also maps to MessageTypes.NULL."""
    event = _make_oh_event(
        message_type=MessageType.HB_V2,
        sia_event=None,
    )
    sia = oh_event_to_sia_event(event)
    assert sia.message_type == MessageTypes.NULL


def test_unknown_message_type_mapping() -> None:
    """Test unknown message type maps to MessageTypes.OH."""
    event = _make_oh_event(message_type=MessageType.DHR)
    sia = oh_event_to_sia_event(event)
    assert sia.message_type == MessageTypes.OH


def test_core_fields() -> None:
    """Test code, ri, account, and panel_id are correctly mapped."""
    event = _make_oh_event()
    sia = oh_event_to_sia_event(event)
    assert sia.code == "BA"
    assert sia.ri == "01"  # from sia_zone
    assert sia.account == "AABBCC"  # from effective_account (system_account)
    assert sia.id == "42"  # panel_id stringified


def test_account_fallback() -> None:
    """Test effective_account falls back to account when system_account is None."""
    event = _make_oh_event(system_account=None, account="112233")
    sia = oh_event_to_sia_event(event)
    assert sia.account == "112233"


def test_receiver_line_formatting() -> None:
    """Test receiver and line get R/L prefix."""
    event = _make_oh_event(receiver="0002", line="0003")
    sia = oh_event_to_sia_event(event)
    assert sia.receiver == "R0002"
    assert sia.line == "L0003"


def test_receiver_line_none_fallback() -> None:
    """Test receiver and line default to 0000 when None."""
    event = _make_oh_event(receiver=None, line=None)
    sia = oh_event_to_sia_event(event)
    assert sia.receiver == "R0000"
    assert sia.line == "L0000"


def test_timestamp_datetime_passthrough() -> None:
    """Test datetime timestamp passes through unchanged."""
    ts = datetime(2025, 6, 15, 12, 30, 0)
    event = _make_oh_event(timestamp=ts)
    sia = oh_event_to_sia_event(event)
    assert sia.timestamp == ts


def test_timestamp_iso_string_parsing() -> None:
    """Test ISO string timestamp is parsed to datetime."""
    event = _make_oh_event(timestamp="2025-06-15T12:30:00")
    sia = oh_event_to_sia_event(event)
    assert isinstance(sia.timestamp, datetime)
    assert sia.timestamp == datetime(2025, 6, 15, 12, 30, 0)


def test_timestamp_none() -> None:
    """Test None timestamp stays None."""
    event = _make_oh_event(timestamp=None)
    sia = oh_event_to_sia_event(event)
    assert sia.timestamp is None


def test_sia_code_lookup() -> None:
    """Test sia_code is looked up from SIA_CODES and copied."""
    event = _make_oh_event(sia_event="BA")
    sia = oh_event_to_sia_event(event)
    assert sia.sia_code is not None
    assert sia.sia_code.code == "BA"
    # Verify it's a copy, not the original
    assert sia.sia_code is not SIA_CODES.get("BA")


def test_sia_code_none_for_unknown_code() -> None:
    """Test sia_code is None for unknown codes."""
    event = _make_oh_event(sia_event="ZZ")
    sia = oh_event_to_sia_event(event)
    assert sia.sia_code is None


def test_sia_code_none_when_no_code() -> None:
    """Test sia_code is None when code is None."""
    event = _make_oh_event(sia_event=None, message_type=MessageType.DHR)
    sia = oh_event_to_sia_event(event)
    assert sia.sia_code is None


def test_crc_bypass_valid_message() -> None:
    """Test msg_crc matches calc_crc so valid_message returns True."""
    event = _make_oh_event()
    sia = oh_event_to_sia_event(event)
    assert sia.msg_crc == sia.calc_crc
    assert sia.valid_message


def test_parse_flags_set() -> None:
    """Test all parse guard flags are set to prevent re-parsing."""
    event = _make_oh_event()
    sia = oh_event_to_sia_event(event)
    assert sia._content_parsed is True
    assert sia._encrypted_content_decrypted is True
    assert sia._adm_parsed is True
    assert sia._sia_added is True
    assert sia._xdata_parsed is True


def test_get_event_data_from_converted_event() -> None:
    """Test get_event_data_from_sia_event produces correct output."""
    ts = datetime(2025, 6, 15, 12, 30, 0)
    event = _make_oh_event(timestamp=ts)
    sia = oh_event_to_sia_event(event)
    data = get_event_data_from_sia_event(sia)

    assert data["message_type"] == "SIA-DCS"
    assert data["receiver"] == "R0001"
    assert data["line"] == "L0001"
    assert data["account"] == "AABBCC"
    assert data["sequence"] == "1234"
    assert data["code"] == "BA"
    assert data["ri"] == "01"
    assert data["id"] == "42"
    assert data["message"] == "Burglary Alarm Zone 1"
    assert data["timestamp"] == "2025-06-15T12:30:00"
    assert data["content"] is None
    assert data["x_data"] is None
    assert data["extended_data"] is None
    assert data["sia_code"]["code"] == "BA"
    assert data["sia_code"]["type"] == "Burglary Alarm"

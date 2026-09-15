"""Test the adaptive lighting transition protocol of the HomeKit bridge."""

import base64

from homeassistant.components.homekit.adaptive_lighting import (
    _transition_as_dict,
    _transition_from_dict,
    interpolate,
    parse_transition_control,
    supported_transition_configuration,
    tlv_decode,
    tlv_encode,
    tlv_encode_list,
    write_variable_uint_le,
)

# A real schedule written by the Home app to a colour temperature light. The
# curve covers 24 hours in 42 points and asks for an update every 60 seconds.
TRANSITION_CONTROL_WRITE = (
    "Av8B/wEBDQImARDE8z2pY8lMD4uJbDajPu+eAgiCLNrVvAAAAAMI7Ig7PwjVT4kDAQEF/wEP"
    "AQQXbEG/AgQcx/1DAwEAAAABEgEEMzMzvwIEAID9QwMEwLAHAAAAARIBBGzBFr8CBMdx+0MD"
    "BEB3GwAAAAESAQT1SR+/AgRyHP1DAwRAdxsAAAABGAEEbMEWvwIEx/H5QwMEQHcbAAQEgMuk"
    "AAAAARIBBLZgC78CBOS49UMDBEB3GwAAAAESAQTv7u6+AgRVVe9DAwRAdxsAAAABEgEEchzH"
    "vgIEx3HoQwMEQHcbAAAAARIBBJqZmb4CBACA4UMDBEB3GwAAAAESAQQC/83MAf9MvgIEAADa"
    "QwMEQHcbAAAAARIBBM3MzL0CBAAA00MDBEB3GwAAAAESAQSJiAi9AgQF/6sqzEMDBEB3GwAA"
    "AAESAQRhCza9AgTkOMZDAwRAdxsAAAABEgEE9UkfvgIEHMfAQwMEQHcbAAAAARIBBGELtr4C"
    "BBzHu0MDBEB3GwAAAAESAQTkOA6/AgQcR7dDAwRAdxsAAAABEgEE6ZM+vwIE5LizQwMEQHcb"
    "AAAAARIBBFuwhb8CBOQ4sUMDBEB3GwAAAAESAQQ5jqO/AgSO469DAwRAdxsAAAABEgEEjuO4"
    "vwIE5DivQwMEQHcbAAAAARIBBKVPur8CBBxHrgL/QwMEQAH/dxsAAAABEgEEpU+6vwIEHMet"
    "QwMEQHcbAAAAARIBBLy7u78CBFXVrUMDBEB3GwAAAAEF/xIBBKVPur8CBBzHrUMDBEB3GwAA"
    "AAEYAQS8u7u/AgRV1a1DAwRAdxsABASA7jYAAAABEgEEpU+6vwIEHMetQwMEQHcbAAAAARIB"
    "BHd3t78CBKsqrkMDBEB3GwAAAAESAQQGW7C/AgSO465DAwRAdxsAAAABEgEEZmamvwIEAICw"
    "QwMEQHcbAAAAARIBBJqZmb8CBAAAskMDBEB3GwAAAAESAQTNzIy/AgQAALVDAwRAdxsAAAAB"
    "EgEE0id9vwIEx3G4QwMEAv9AdxsAAAAB9wESAQSUPmm/AgQ5jr1DAwRAdxsAAAABEgEEMzMz"
    "vwIEAADEQwMEQHcbAAAAARIBBFuwBb8FtwIEchzMQwMEQHcbAAAAARIBBAZbML8CBMfx10MD"
    "BEB3GwAAAAESAQRyHEe/AgSOY+NDAwRAdxsAAAABEgEEsAVbvwIEHMfuQwMEQHcbAAAAARIB"
    "BLAFW78CBBxH+EMDBEB3GwAAAAESAQTv7m6/AgSrqv5DAwRAdxsAAAABEgEE3t1dvwIEVVX+"
    "QwMEQHcbAAAAARIBBBdsQb8CBBzH/UMDBIDGEwACAQoDDAEECgAAAAIEZAAAAAYCYOoIBMAn"
    "CQA="
)


def test_write_variable_uint_le() -> None:
    """Values are encoded in the smallest little-endian width."""
    assert write_variable_uint_le(2) == b"\x02"
    assert write_variable_uint_le(300) == b"\x2c\x01"
    assert write_variable_uint_le(70000) == b"\x70\x11\x01\x00"


def test_tlv_encode_splits_long_values() -> None:
    """A value longer than 255 bytes is split across repeated entries."""
    assert tlv_encode(0x01, b"\x02") == b"\x01\x01\x02"
    assert (
        tlv_encode(0x09, b"\xaa" * 256)
        == b"\x09\xff" + b"\xaa" * 255 + b"\x09\x01\xaa"
    )


def test_tlv_list_uses_the_empty_delimiter() -> None:
    """Repeated entries are separated by a zero length TLV, as HAP expects."""
    assert (
        tlv_encode_list(0x01, [b"\xaa", b"\xbb"])
        == b"\x01\x01\xaa\x00\x00\x01\x01\xbb"
    )
    assert tlv_encode_list(0x01, []) == b"\x01\x00"


def test_tlv_decode_rejoins_split_values() -> None:
    """Decoding is the inverse of encoding for values of any length."""
    value = bytes(range(256)) * 2
    assert tlv_decode(tlv_encode(0x07, value)) == [(0x07, value)]


def test_supported_transition_configuration() -> None:
    """Brightness and colour temperature are advertised with their iids."""
    encoded = base64.b64decode(supported_transition_configuration(2, 4))
    assert encoded == bytes.fromhex("0106010102020101" "0000" "0106010104020102")


def test_parse_real_transition_control_write() -> None:
    """A schedule from the Home app is parsed into a usable curve."""
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)

    assert transition is not None
    assert len(transition.curve) == 42
    assert transition.update_interval == 60000
    assert transition.notify_threshold == 600000
    assert (transition.min_multiplier, transition.max_multiplier) == (10, 100)
    assert len(transition.transition_id) == 16


def test_interpolate_covers_a_full_day() -> None:
    """The schedule walks a full day of colour temperatures.

    The Home app may send points slightly outside the advertised range of the
    characteristic (it sent 509 mireds for a light advertising 500), which is
    why the controller clamps the interpolated value before writing it.
    """
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)
    assert transition is not None
    start = transition.start_millis + transition.time_millis_offset

    values = []
    for minutes in range(0, 24 * 60, 37):
        value = interpolate(transition, start + minutes * 60000)
        if value is None:
            break
        assert 100 <= value <= 600
        values.append(value)

    assert len(values) > 30
    assert max(values) - min(values) > 100


def test_interpolate_returns_none_past_the_end() -> None:
    """The schedule only covers 24 hours; afterwards there is nothing to apply."""
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)
    assert transition is not None
    start = transition.start_millis + transition.time_millis_offset
    assert interpolate(transition, start + 48 * 3600 * 1000) is None


def test_transition_survives_serialization() -> None:
    """A stored schedule is restored unchanged after a restart."""
    transition = parse_transition_control(TRANSITION_CONTROL_WRITE)
    assert transition is not None
    assert _transition_from_dict(_transition_as_dict(transition)) == transition


def test_parse_rejects_an_empty_write() -> None:
    """Clearing the characteristic does not produce a transition."""
    assert parse_transition_control(base64.b64encode(b"").decode()) is None

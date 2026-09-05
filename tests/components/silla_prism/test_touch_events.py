"""Unit tests for Prism touch event parsing."""

from homeassistant.components.silla_prism.touch_events import (
    normalize_touch_payload,
    touch_payload_matches,
)


def test_parses_comma_and_json_like_sequences() -> None:
    """Test numeric touch payload sequences."""
    assert normalize_touch_payload("1") == (1,)
    assert normalize_touch_payload("1,1") == (1, 1)
    assert normalize_touch_payload("[1, 1]") == (1, 1)


def test_parses_textual_events() -> None:
    """Test textual touch payload aliases."""
    assert normalize_touch_payload("single") == (1,)
    assert normalize_touch_payload("double_touch") == (2,)
    assert normalize_touch_payload("pressione lunga") == (3,)


def test_double_accepts_repeated_touch_and_numeric_code() -> None:
    """Test double touch accepts firmware payload variants."""
    accepted = ((1, 1), (2,))

    assert touch_payload_matches("1,1", accepted)
    assert touch_payload_matches("2", accepted)
    assert touch_payload_matches("double", accepted)
    assert not touch_payload_matches("1", accepted)


def test_ignores_empty_or_unknown_payloads() -> None:
    """Test empty and unknown payloads are ignored."""
    assert normalize_touch_payload("") is None
    assert normalize_touch_payload(None) is None
    assert not touch_payload_matches("knock", ((1,),))

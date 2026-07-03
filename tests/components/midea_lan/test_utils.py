"""Tests for midea_lan utils."""

from unittest.mock import patch

from homeassistant.components.midea_lan.utils import decode_preset_account


def test_decode_preset_account_odd_hex_length_is_padded() -> None:
    """Test decode_preset_account pads odd-length hex before decoding."""
    with patch(
        "homeassistant.components.midea_lan.utils.PRESET_ACCOUNT_DATA",
        [0, 1],
    ):
        assert decode_preset_account(1) == "\x01"


def test_decode_preset_account_even_hex_length() -> None:
    """Test decode_preset_account decodes even-length hex directly."""
    with patch(
        "homeassistant.components.midea_lan.utils.PRESET_ACCOUNT_DATA",
        [0, 0x6162],
    ):
        assert decode_preset_account(1) == "ab"

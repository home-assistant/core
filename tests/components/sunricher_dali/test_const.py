"""Test the Sunricher DALI const module."""

import pytest

from homeassistant.components.sunricher_dali.const import sn_to_mac


def test_sn_to_mac_conversion() -> None:
    """Test serial number to MAC address conversion."""
    assert sn_to_mac("6A242121110E") == "6a:24:21:21:11:0e"
    assert sn_to_mac("6a242121110e") == "6a:24:21:21:11:0e"
    assert sn_to_mac(" 6A242121110E ") == "6a:24:21:21:11:0e"


def test_sn_to_mac_invalid_length() -> None:
    """Test that invalid serial number length raises ValueError."""
    with pytest.raises(ValueError, match="Invalid serial number length"):
        sn_to_mac("6A2421")
    with pytest.raises(ValueError, match="Invalid serial number length"):
        sn_to_mac("6A242121110E00")

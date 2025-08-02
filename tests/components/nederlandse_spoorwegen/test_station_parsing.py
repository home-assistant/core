"""Test station string parsing for NS integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.nederlandse_spoorwegen.api import NSAPIWrapper


@pytest.mark.parametrize(
    ("station_str", "expected_code", "expected_name"),
    [
        ("HAGEN Hagen Hbf", "HAGEN", "Hagen Hbf"),
        ("WUPPV Wuppertal-Vohwinkel", "WUPPV", "Wuppertal-Vohwinkel"),
        ("DUSSEL Düsseldorf Hbf", "DUSSEL", "Düsseldorf Hbf"),
        ("OBERHS Oberhausen-Sterkrade", "OBERHS", "Oberhausen-Sterkrade"),
        ("BASELB Basel Bad Bf", "BASELB", "Basel Bad Bf"),
        ("BUENDE Bünde (Westf)", "BUENDE", "Bünde (Westf)"),
        ("BRUSN Brussel-Noord", "BRUSN", "Brussel-Noord"),
        ("AIXTGV Aix-en-Provence TGV", "AIXTGV", "Aix-en-Provence TGV"),
        ("VALTGV Valence TGV", "VALTGV", "Valence TGV"),
    ],
)
def test_station_parsing(station_str, expected_code, expected_name) -> None:
    """Test that station string is parsed into code and name correctly."""
    # Create a mock hass object for the API wrapper
    mock_hass = MagicMock()
    api_wrapper = NSAPIWrapper(mock_hass, "dummy_key")
    stations = [station_str]
    mapping = api_wrapper.build_station_mapping(stations)

    # Check that the station was parsed correctly
    assert expected_code.upper() in mapping
    assert mapping[expected_code.upper()] == expected_name

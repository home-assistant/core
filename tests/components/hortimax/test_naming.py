"""Test turning HortOS identifiers into readable names."""

import pytest

from homeassistant.components.hortimax.naming import (
    disambiguate_source_names,
    readout_display_name,
    split_camel,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("VentPositionLeewardSide", "Vent position leeward side"),
        # Acronyms stay intact, and the word after them is split off.
        ("CO2Level", "CO2 level"),
        ("ECMeasured", "EC measured"),
        ("Temperature", "Temperature"),
        ("Supplementary lighting group 005", "Supplementary lighting group 005"),
        # Nothing to split on.
        ("", ""),
        ("-", "-"),
    ],
)
def test_split_camel(value: str, expected: str) -> None:
    """Test CamelCase identifiers become sentences."""
    assert split_camel(value) == expected


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        # 'Measured' is the default kind and is dropped.
        ("OutsideTemperature-Measured", "Outside temperature"),
        # Including Ridder's typo of it.
        ("IrrigationVolume-Measuered", "Irrigation volume"),
        (
            "VentPositionLeewardSide-Calculated",
            "Vent position leeward side (calculated)",
        ),
        (
            "MaximumPipeTemperature-ActualSetting",
            "Maximum pipe temperature (actual setting)",
        ),
        ("OutsideTemperature", "Outside temperature"),
    ],
)
def test_readout_display_name(identifier: str, expected: str) -> None:
    """Test readout identifiers become entity names."""
    assert readout_display_name(identifier) == expected


def test_disambiguate_source_names() -> None:
    """Test clashing source names get the least extra text needed."""
    resolved = disambiguate_source_names(
        {
            # Unique: left alone.
            "WeatherStation::Weather station 001": (
                "Weerstation",
                "WeatherStation",
                "Weather station 001",
            ),
            # Same name, different type: the type is appended.
            "Screen::Screen 001": ("OV1 Tropen", "Screen", "Screen 001"),
            "VentilationGroup::Ventilation group 001": (
                "OV1 Tropen",
                "VentilationGroup",
                "Ventilation group 001",
            ),
            # Same name *and* type: the number of the technical name follows.
            "SupplementaryLightingGroup::Supplementary lighting group 005": (
                "Reserve",
                "SupplementaryLightingGroup",
                "Supplementary lighting group 005",
            ),
            "SupplementaryLightingGroup::Supplementary lighting group 006": (
                "Reserve",
                "SupplementaryLightingGroup",
                "Supplementary lighting group 006",
            ),
        }
    )

    assert resolved == {
        "WeatherStation::Weather station 001": "Weerstation",
        "Screen::Screen 001": "OV1 Tropen screen",
        "VentilationGroup::Ventilation group 001": "OV1 Tropen ventilation group",
        "SupplementaryLightingGroup::Supplementary lighting group 005": (
            "Reserve supplementary lighting group 005"
        ),
        "SupplementaryLightingGroup::Supplementary lighting group 006": (
            "Reserve supplementary lighting group 006"
        ),
    }


def test_disambiguate_falls_back_to_the_whole_name() -> None:
    """Test sources without a number in their technical name still differ."""
    resolved = disambiguate_source_names(
        {
            "Screen::Left": ("Reserve", "Screen", "Left"),
            "Screen::Right": ("Reserve", "Screen", "Right"),
        }
    )

    assert resolved == {
        "Screen::Left": "Reserve screen Left",
        "Screen::Right": "Reserve screen Right",
    }

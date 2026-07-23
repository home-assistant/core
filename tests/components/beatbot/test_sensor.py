"""Tests for Beatbot sensor category support."""

from homeassistant.components.beatbot.iot.category import (
    BATTERY_CATEGORIES,
    CATEGORY_MAP,
)


def test_clean_base_station_has_no_battery() -> None:
    """The mains-powered clean base station must not get a battery entity."""
    category = CATEGORY_MAP["clean_base_station"]

    assert category not in BATTERY_CATEGORIES


def test_mobile_devices_have_battery() -> None:
    """Mobile product categories retain their battery entities."""
    assert CATEGORY_MAP["pool_clean_bot"] in BATTERY_CATEGORIES
    assert CATEGORY_MAP["lawn_mower"] in BATTERY_CATEGORIES

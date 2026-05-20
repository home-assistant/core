"""Tests for Kii Audio select entities."""

from copy import deepcopy

from homeassistant.components.kii_audio.select import (
    SELECT_DESCRIPTIONS,
    KiiAudioZoneSelect,
)

from .conftest import ZONE_ID, FakeCoordinator, make_zone


def _description(key: str):
    """Return a select description by key."""
    return next(
        description for description in SELECT_DESCRIPTIONS if description.key == key
    )


def test_analog_sensitivity_select() -> None:
    """Test analogue sensitivity select maps boolean values."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneSelect(
        coordinator, zone, _description("analog_input_sensitivity")
    )

    assert entity.options == ["Low", "High"]
    assert entity.current_option == "Low"


async def test_analog_sensitivity_select_sends_boolean() -> None:
    """Test analogue sensitivity selection sends a boolean setting."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneSelect(
        coordinator, zone, _description("analog_input_sensitivity")
    )

    await entity.async_select_option("High")

    assert coordinator.calls == [
        ("setting", (ZONE_ID, "audio.analogHighSensitivity", True))
    ]


def test_latency_select() -> None:
    """Test latency select maps raw values to labels."""
    zone = make_zone()
    zone["settings"]["audio"]["latency"] = "match"
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneSelect(coordinator, zone, _description("latency"))

    assert entity.options == ["Optimum", "Minimum", "Match Kii Three"]
    assert entity.current_option == "Match Kii Three"


async def test_latency_select_sends_raw_value() -> None:
    """Test latency selection sends a raw Kii value."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneSelect(coordinator, zone, _description("latency"))

    await entity.async_select_option("Minimum")

    assert coordinator.calls == [("setting", (ZONE_ID, "audio.latency", "minimum"))]

"""Tests for Kii Audio switch entities."""

from copy import deepcopy

from homeassistant.components.kii_audio.switch import (
    SWITCH_DESCRIPTIONS,
    KiiAudioZoneSwitch,
)

from .conftest import ZONE_ID, FakeCoordinator, make_zone


def _description(key: str):
    """Return a switch description by key."""
    return next(
        description for description in SWITCH_DESCRIPTIONS if description.key == key
    )


def test_tone_control_switch_reports_state() -> None:
    """Test tone control switch reads the enabled setting."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneSwitch(coordinator, zone, _description("tone_control"))

    assert entity.is_on is True


async def test_tone_control_switch_sends_setting() -> None:
    """Test tone control switch sends boolean setting requests."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioZoneSwitch(coordinator, zone, _description("tone_control"))

    await entity.async_turn_off()
    await entity.async_turn_on()

    assert coordinator.calls == [
        ("setting", (ZONE_ID, "audio.toneControl.enabled", False)),
        ("setting", (ZONE_ID, "audio.toneControl.enabled", True)),
    ]

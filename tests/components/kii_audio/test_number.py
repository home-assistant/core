"""Tests for Kii Audio number entities."""

from copy import deepcopy

from homeassistant.components.kii_audio.number import (
    TONE_CONTROL_DESCRIPTIONS,
    KiiAudioToneControlNumber,
)

from .conftest import ZONE_ID, FakeCoordinator, make_zone


def _description(key: str):
    """Return a number description by key."""
    return next(
        description
        for description in TONE_CONTROL_DESCRIPTIONS
        if description.key == key
    )


def test_tone_control_number_reports_native_value() -> None:
    """Test bass and treble values are read from tone control settings."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))

    bass = KiiAudioToneControlNumber(coordinator, zone, _description("bass"))
    treble = KiiAudioToneControlNumber(coordinator, zone, _description("treble"))

    assert bass.native_value == 1.2
    assert treble.native_value == -0.8


def test_tone_control_step_follows_advanced_mode() -> None:
    """Test tone control step size depends on advanced mode."""
    simple_zone = make_zone(advanced_mode=False)
    advanced_zone = make_zone(advanced_mode=True)

    simple = KiiAudioToneControlNumber(
        FakeCoordinator(deepcopy(simple_zone)), simple_zone, _description("bass")
    )
    advanced = KiiAudioToneControlNumber(
        FakeCoordinator(deepcopy(advanced_zone)), advanced_zone, _description("bass")
    )

    assert simple.native_step == 0.5
    assert advanced.native_step == 0.1


async def test_tone_control_number_rounds_to_current_step() -> None:
    """Test tone control requests are rounded to the active step size."""
    simple_zone = make_zone(advanced_mode=False)
    simple_coordinator = FakeCoordinator(deepcopy(simple_zone))
    simple = KiiAudioToneControlNumber(
        simple_coordinator, simple_zone, _description("bass")
    )

    advanced_zone = make_zone(advanced_mode=True)
    advanced_coordinator = FakeCoordinator(deepcopy(advanced_zone))
    advanced = KiiAudioToneControlNumber(
        advanced_coordinator, advanced_zone, _description("bass")
    )

    await simple.async_set_native_value(1.26)
    await advanced.async_set_native_value(1.26)

    assert simple_coordinator.calls == [
        ("setting", (ZONE_ID, "audio.toneControl.low.gain", 1.5))
    ]
    assert advanced_coordinator.calls == [
        ("setting", (ZONE_ID, "audio.toneControl.low.gain", 1.3))
    ]


def test_tone_control_number_uses_zone_device_info() -> None:
    """Test tone control numbers attach to the zone-level device."""
    zone = make_zone()
    coordinator = FakeCoordinator(deepcopy(zone))
    entity = KiiAudioToneControlNumber(coordinator, zone, _description("bass"))

    assert entity.device_info["identifiers"] == {("kii_audio", "system-id_zone-id")}
    assert entity.device_info["manufacturer"] == "Kii Audio GmbH"
    assert entity.device_info["model"] == "Kii Seven"
    assert entity.device_info["name"] == "Office"

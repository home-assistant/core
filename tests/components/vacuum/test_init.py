"""The tests for the Vacuum entity integration."""

from __future__ import annotations

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.core import HomeAssistant


async def test_supported_features_compat(hass: HomeAssistant) -> None:
    """Test StateVacuumEntity using deprecated feature constants features."""

    features = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
    )

    class _LegacyConstantsStateVacuum(StateVacuumEntity):
        _attr_supported_features = int(features)
        _attr_fan_speed_list = ["silent", "normal", "pet hair"]

    entity = _LegacyConstantsStateVacuum()
    assert isinstance(entity.supported_features, int)
    assert entity.supported_features == int(features)
    assert entity.supported_features_compat is (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
    )
    assert entity.state_attributes == {
        "battery_level": None,
        "battery_icon": "mdi:battery-unknown",
        "fan_speed": None,
    }
    assert entity.capability_attributes == {
        "fan_speed_list": ["silent", "normal", "pet hair"]
    }
    assert entity._deprecated_supported_features_reported

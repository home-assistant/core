"""The tests for the Vacuum entity integration."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.components.vacuum import (
    DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant

from . import MockVacuum, create_entity


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_CLEAN_SPOT, STATE_CLEANING),
        (SERVICE_PAUSE, STATE_PAUSED),
        (SERVICE_RETURN_TO_BASE, STATE_RETURNING),
        (SERVICE_START, STATE_CLEANING),
        (SERVICE_STOP, STATE_IDLE),
    ],
)
async def test_state_services(
    hass: HomeAssistant, config_flow_fixture: None, service: str, expected_state: str
) -> None:
    """Test get vacuum service that affect state."""

    entity0 = await create_entity(hass)

    await hass.services.async_call(
        DOMAIN,
        service,
        {"entity_id": entity0.entity_id},
        blocking=True,
    )
    vacuum_state = hass.states.get(entity0.entity_id)

    assert vacuum_state.state == expected_state


async def test_fan_speed(hass: HomeAssistant, config_flow_fixture: None) -> None:
    """Test set vacuum fan speed."""

    entity0 = await create_entity(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {"entity_id": entity0.entity_id, "fan_speed": "high"},
        blocking=True,
    )

    assert entity0.fan_speed == "high"


async def test_locate(hass: HomeAssistant, config_flow_fixture: None) -> None:
    """Test vacuum locate."""

    calls = []

    class MockVacuumWithLocation(MockVacuum):
        def __init__(self, calls: list[str], **kwargs) -> None:
            super().__init__()
            self._attr_supported_features = (
                self.supported_features | VacuumEntityFeature.LOCATE
            )
            self._calls = calls

        def locate(self, **kwargs: Any) -> None:
            self._calls.append("locate")

    entity0 = await create_entity(hass, mock_vacuum=MockVacuumWithLocation, calls=calls)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOCATE,
        {"entity_id": entity0.entity_id},
        blocking=True,
    )

    assert "locate" in calls


async def test_send_command(hass: HomeAssistant, config_flow_fixture: None) -> None:
    """Test Vacuum send command."""

    strings = []

    class MockVacuumWithLocation(MockVacuum):
        def __init__(self, strings: list[str], **kwargs) -> None:
            super().__init__()
            self._attr_supported_features = (
                self.supported_features | VacuumEntityFeature.SEND_COMMAND
            )
            self._strings = strings

        def send_command(
            self,
            command: str,
            params: dict[str, Any] | list[Any] | None = None,
            **kwargs: Any,
        ) -> None:
            if command == "add_str":
                self._strings.append(params["str"])

    entity0 = await create_entity(
        hass,
        mock_vacuum=MockVacuumWithLocation,
        strings=strings,
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            "entity_id": entity0.entity_id,
            "command": "add_str",
            "params": {"str": "test"},
        },
        blocking=True,
    )

    assert "test" in strings


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

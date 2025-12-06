"""Tests for the Actron Air switch platform."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.actron_air import switch as actron_switch
from homeassistant.components.actron_air.const import DOMAIN
from homeassistant.components.actron_air.coordinator import (
    ActronAirRuntimeData,
    ActronAirSystemCoordinator,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class MockUserAirconSettings:
    """Mock Actron Air user aircon settings object."""

    def __init__(self, *, turbo_supported: bool = True) -> None:
        """Initialize mock settings with default values."""
        self.away_mode = False
        self.continuous_fan_enabled = False
        self.quiet_mode_enabled = False
        self.turbo_enabled = False
        self.turbo_supported = turbo_supported

        self.set_away_mode = AsyncMock()
        self.set_continuous_mode = AsyncMock()
        self.set_quiet_mode = AsyncMock()
        self.set_turbo_mode = AsyncMock()


async def _create_coordinator(
    hass: HomeAssistant, user_settings: MockUserAirconSettings
) -> ActronAirSystemCoordinator:
    """Create a coordinator instance backed by mocked API data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    api = MagicMock()
    api.update_status = AsyncMock()
    api.state_manager = MagicMock()

    status = SimpleNamespace(user_aircon_settings=user_settings)
    api.state_manager.get_status.return_value = status

    coordinator = ActronAirSystemCoordinator(
        hass,
        config_entry,
        api,
        {"serial": "ABC123"},
    )
    coordinator.data = status
    return coordinator


async def test_switch_setup_adds_all_entities_when_turbo_supported(
    hass: HomeAssistant,
) -> None:
    """Test that switch setup adds all entities when turbo is supported."""
    user_settings = MockUserAirconSettings(turbo_supported=True)
    coordinator = await _create_coordinator(hass, user_settings)

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.runtime_data = ActronAirRuntimeData(
        api=MagicMock(),
        system_coordinators={coordinator.serial_number: coordinator},
    )

    added: list = []

    def _async_add_entities(entities):
        added.extend(entities)

    await actron_switch.async_setup_entry(hass, entry, _async_add_entities)

    assert len(added) == 4
    assert any(isinstance(entity, actron_switch.TurboModeSwitch) for entity in added)
    assert {type(entity) for entity in added} == {
        actron_switch.AwayModeSwitch,
        actron_switch.ContinuousFanSwitch,
        actron_switch.QuietModeSwitch,
        actron_switch.TurboModeSwitch,
    }


async def test_switch_setup_excludes_turbo_when_not_supported(
    hass: HomeAssistant,
) -> None:
    """Test that the turbo switch is not added when unsupported."""
    user_settings = MockUserAirconSettings(turbo_supported=False)
    coordinator = await _create_coordinator(hass, user_settings)

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.runtime_data = ActronAirRuntimeData(
        api=MagicMock(),
        system_coordinators={coordinator.serial_number: coordinator},
    )

    added: list = []

    def _async_add_entities(entities):
        added.extend(entities)

    await actron_switch.async_setup_entry(hass, entry, _async_add_entities)

    assert len(added) == 3
    assert not any(
        isinstance(entity, actron_switch.TurboModeSwitch) for entity in added
    )


@pytest.mark.parametrize(
    ("entity_cls", "attr_name", "method_name"),
    [
        (actron_switch.AwayModeSwitch, "away_mode", "set_away_mode"),
        (
            actron_switch.ContinuousFanSwitch,
            "continuous_fan_enabled",
            "set_continuous_mode",
        ),
        (actron_switch.QuietModeSwitch, "quiet_mode_enabled", "set_quiet_mode"),
        (actron_switch.TurboModeSwitch, "turbo_enabled", "set_turbo_mode"),
    ],
)
async def test_switch_turn_on_off_calls_api(
    hass: HomeAssistant, entity_cls, attr_name, method_name
) -> None:
    """Ensure turning switches on/off calls the expected API helpers."""
    user_settings = MockUserAirconSettings(turbo_supported=True)
    setattr(user_settings, attr_name, False)

    coordinator = await _create_coordinator(hass, user_settings)
    entity = entity_cls(coordinator)

    assert entity.is_on is False

    api_method = getattr(user_settings, method_name)
    api_method.assert_not_called()

    await entity.async_turn_on()
    api_method.assert_awaited_once_with(True)

    await entity.async_turn_off()
    assert api_method.await_count == 2
    assert api_method.await_args_list[-1].args == (False,)

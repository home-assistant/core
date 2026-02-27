"""Test platform setup helpers and utility branches."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from homeassistant.exceptions import HomeAssistantError

from homeassistant.components.madvr import binary_sensor, button, remote, select, sensor, switch
from homeassistant.components.madvr.coordinator import MadvrEnvyCoordinator
from homeassistant.components.madvr.entity import MadvrEnvyEntity


async def test_platform_setup_entity_counts(hass, mock_envy_client):
    """Test platform setup entity creation and advanced filtering."""
    coordinator = MadvrEnvyCoordinator(hass, mock_envy_client)
    await coordinator.async_start()

    basic_entry = SimpleNamespace(
        runtime_data=SimpleNamespace(coordinator=coordinator),
        options={"enable_advanced_entities": False},
    )
    full_entry = SimpleNamespace(
        runtime_data=SimpleNamespace(coordinator=coordinator),
        options={"enable_advanced_entities": True},
    )

    added_basic: list[object] = []
    added_full: list[object] = []

    await sensor.async_setup_entry(hass, basic_entry, added_basic.extend)
    await sensor.async_setup_entry(hass, full_entry, added_full.extend)
    assert len(added_basic) == len(sensor.SENSORS) - 3
    assert len(added_full) == len(sensor.SENSORS)

    added_buttons_basic: list[object] = []
    added_buttons_full: list[object] = []
    await button.async_setup_entry(hass, basic_entry, added_buttons_basic.extend)
    await button.async_setup_entry(hass, full_entry, added_buttons_full.extend)
    assert len(added_buttons_basic) < len(added_buttons_full)

    added_binary: list[object] = []
    await binary_sensor.async_setup_entry(hass, full_entry, added_binary.extend)
    assert len(added_binary) == 1

    added_switch: list[object] = []
    await switch.async_setup_entry(hass, full_entry, added_switch.extend)
    assert len(added_switch) == 1

    added_select: list[object] = []
    await select.async_setup_entry(hass, full_entry, added_select.extend)
    assert len(added_select) >= 2

    added_remote: list[object] = []
    await remote.async_setup_entry(hass, full_entry, added_remote.extend)
    assert len(added_remote) == 1

    await coordinator.async_shutdown()


def test_temperature_value_helper_branches():
    """Test temperature helper fallback behavior."""
    assert sensor._temperature_value({}, 0) is None
    assert sensor._temperature_value({"temperatures": (1,)}, 1) is None
    assert sensor._temperature_value({"temperatures": ("x",)}, 0) is None
    assert sensor._active_profile_value({}) is None
    assert (
        sensor._active_profile_value({"active_profile_group": "1", "active_profile_index": 2})
        == "1: 2"
    )
    assert (
        sensor._active_profile_value(
            {
                "active_profile_group": "1",
                "active_profile_index": 2,
                "profile_groups": {"1": "Cinema"},
                "profiles": {"1_2": "Night"},
            }
        )
        == "Cinema: Night"
    )


def test_select_profile_id_parsing_branches():
    """Test profile id parsing edge cases."""
    assert select._parse_profile_id("1_2", None) == ("1", 2)
    assert select._parse_profile_id("2", "1") == ("1", 2)
    assert select._parse_profile_id("invalid", "1") is None
    assert select._build_profile_options({}) == []


class _DummyEntity(MadvrEnvyEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "dummy")


async def test_entity_execute_wraps_command_errors(hass, mock_envy_client):
    """Test command errors are translated to HomeAssistantError."""
    coordinator = MadvrEnvyCoordinator(hass, mock_envy_client)
    await coordinator.async_start()

    entity = _DummyEntity(coordinator)

    async def _failing_command():
        raise TimeoutError

    with pytest.raises(HomeAssistantError):
        await entity._execute("test", _failing_command)

    await coordinator.async_shutdown()

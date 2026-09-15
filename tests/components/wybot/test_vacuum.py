"""Tests for the WyBot vacuum platform."""

from unittest.mock import AsyncMock

import pytest
from wybot.dp_models import (
    Battery,
    CleaningMode,
    CleaningStatus,
    Dock,
    DockConnectionStatus,
)

from homeassistant.components.vacuum import VacuumActivity, VacuumEntityFeature
from homeassistant.components.wybot.vacuum import WyBotVacuum
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .wybot_platform_helpers import (
    add_entity,
    dp,
    make_coordinator,
    make_group,
    setup_integration,
)

IDX = "grp1"


def _coord(hass: HomeAssistant, device_dps=None, docker_dps=None, **kwargs):
    """Coord."""
    group = make_group(
        device_dps=device_dps or {}, docker_dps=docker_dps or {}, **kwargs
    )
    coord, entry = make_coordinator(hass, {IDX: group})
    return coord, entry, group


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Setting up a device registers a single vacuum entity."""
    entry = await setup_integration(hass, {IDX: make_group()})
    ent_reg = er.async_get(hass)
    vacuums = [
        e
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.domain == "vacuum"
    ]
    assert len(vacuums) == 1


async def test_basic_properties(hass: HomeAssistant) -> None:
    """Test basic properties."""
    coord, _, _ = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.unique_id == "grp1"
    assert ent.available is True
    assert ent.fan_speed_list == CleaningMode.CLEANING_MODES
    assert ent.supported_features == (
        VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
    )
    info = ent.device_info
    assert info["identifiers"] == {("wybot", "grp1")}
    assert info["name"] == "My Pool"
    assert info["model"] == "S2 Pro"
    assert ("bluetooth", "cc:ba:97:93:2a:96") in info["connections"]


async def test_available_branches(hass: HomeAssistant) -> None:
    """Test available branches."""
    coord, _, group = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    coord._connection_available = False
    assert ent.available is False
    coord._connection_available = True
    ent._data = None
    assert ent.available is False
    ent._data = group
    coord.data = {"other": group}
    assert ent.available is False


async def test_available_requires_group_freshness(hass: HomeAssistant) -> None:
    """Availability follows this group's own BLE/MQTT freshness, not HTTP/siblings."""
    coord, _, group = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    # Helper primed a recent BLE poll for this group -> available.
    assert ent.available is True
    # Drop this group's freshness: an account-level HTTP success alone must not
    # keep it available.
    coord._last_ble_poll.clear()
    coord._last_mqtt_data.clear()
    coord._last_http_success = dt_util.utcnow()
    assert ent.available is False
    # A recent MQTT message for this group's device restores availability.
    coord._last_mqtt_data[group.device.device_id] = dt_util.utcnow()
    assert ent.available is True


async def test_device_info_fallbacks(hass: HomeAssistant) -> None:
    # No data -> Unknown/Unknown, no connections/via.
    """Test device info fallbacks."""
    coord, _, _group = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    ent._data = None
    info = ent.device_info
    assert info["name"] == "Unknown"
    assert info["model"] == "Unknown"
    assert "connections" not in info

    # name falsy -> device_name.
    group2 = make_group(name="")
    coord2, _ = make_coordinator(hass, {IDX: group2})
    ent2 = WyBotVacuum(idx=IDX, coordinator=coord2)
    assert ent2.device_info["name"] == "Robot"
    # name and device_name falsy -> device_type.
    group2.device.device_name = ""
    assert ent2.device_info["name"] == "S2 Pro"


async def test_device_info_no_ble_no_docker(hass: HomeAssistant) -> None:
    """Test device info no ble no docker."""
    group = make_group(with_docker=False)
    group.device.ble_name = ""
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    info = ent.device_info
    assert "connections" not in info


async def test_activity_none_when_no_data(hass: HomeAssistant) -> None:
    """Test activity none when no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.activity is None


async def test_activity_returning_via_cleaning_status(hass: HomeAssistant) -> None:
    # CleaningStatus data 04 -> RETURNING_TO_DOCK.
    """Test activity returning via cleaning status."""
    coord, _, _ = _coord(
        hass, device_dps={"0": dp(CleaningStatus, id=0, type=4, len=1, data="04")}
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.RETURNING


async def test_activity_returning_via_dock_dp(hass: HomeAssistant) -> None:
    # Dock DP 11 data 01 -> RETURNING.
    """Test activity returning via dock dp."""
    coord, _, _ = _coord(
        hass, device_dps={"11": dp(Dock, id=11, type=4, len=1, data="01")}
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.RETURNING


async def test_activity_docked_via_dock_dp(hass: HomeAssistant) -> None:
    # Dock DP 11 data 00 -> DOCKED.
    """Test activity docked via dock dp."""
    coord, _, _ = _coord(
        hass, device_dps={"11": dp(Dock, id=11, type=4, len=1, data="00")}
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.DOCKED


async def test_activity_docked_via_dock_connection(hass: HomeAssistant) -> None:
    """Test activity docked via dock connection."""
    coord, _, _ = _coord(
        hass,
        device_dps={"213": dp(DockConnectionStatus, id=213, type=4, len=1, data="01")},
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.DOCKED


async def test_activity_docked_via_battery(hass: HomeAssistant) -> None:
    """Test activity docked via battery."""
    coord, _, _ = _coord(
        hass, device_dps={"50": dp(Battery, id=50, type=0, len=2, data="0132")}
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.DOCKED


async def test_activity_cleaning(hass: HomeAssistant) -> None:
    """Test activity cleaning."""
    coord, _, _ = _coord(
        hass, device_dps={"0": dp(CleaningStatus, id=0, type=4, len=1, data="03")}
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.CLEANING


async def test_activity_cleaning_overrides_stale_dock_returning(
    hass: HomeAssistant,
) -> None:
    """An active CLEANING status wins over a stale dock RETURNING DP."""
    coord, _, _ = _coord(
        hass,
        device_dps={
            "0": dp(CleaningStatus, id=0, type=4, len=1, data="03"),
            "11": dp(Dock, id=11, type=4, len=1, data="01"),  # stale RETURNING
        },
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.CLEANING


async def test_activity_cleaning_overrides_stale_charging(hass: HomeAssistant) -> None:
    """An active CLEANING status wins over a stale charging/docked battery DP."""
    coord, _, _ = _coord(
        hass,
        device_dps={
            "0": dp(CleaningStatus, id=0, type=4, len=1, data="03"),
            # Retained stale battery DP that would otherwise infer DOCKED.
            "50": dp(Battery, id=50, type=0, len=2, data="0132"),
        },
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.CLEANING


async def test_activity_idle_when_stopped(hass: HomeAssistant) -> None:
    # CleaningStatus 01 -> STOPPED -> IDLE. Battery not plugged in so not docked.
    """A stopped robot reports IDLE, not paused."""
    coord, _, _ = _coord(
        hass,
        device_dps={
            "0": dp(CleaningStatus, id=0, type=4, len=1, data="01"),
            "50": dp(Battery, id=50, type=0, len=2, data="004b"),
        },
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity == VacuumActivity.IDLE


async def test_activity_none_when_no_dps(hass: HomeAssistant) -> None:
    """Test activity none when no dps."""
    coord, _, _ = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.activity is None


async def test_fan_speed(hass: HomeAssistant) -> None:
    """Test fan speed."""
    coord, _, _ = _coord(
        hass, device_dps={"1": dp(CleaningMode, id=1, type=4, len=1, data="01")}
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.fan_speed == "Wall"


async def test_fan_speed_no_data(hass: HomeAssistant) -> None:
    """Test fan speed no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.fan_speed is None


async def test_fan_speed_dp_missing(hass: HomeAssistant) -> None:
    """Test fan speed dp missing."""
    coord, _, _ = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    assert ent.fan_speed is None


async def test_commands_success(hass: HomeAssistant) -> None:
    """Test commands success."""
    coord, _, _ = _coord(hass)
    coord.async_send_command = AsyncMock(return_value=True)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    await ent.async_start()
    await ent.async_stop()
    await ent.async_return_to_base()
    await ent.async_set_fan_speed("Wall")
    assert coord.async_send_command.await_count == 4


async def test_commands_failure_raises(hass: HomeAssistant) -> None:
    """Test commands failure raises."""
    coord, _, _ = _coord(hass)
    coord.async_send_command = AsyncMock(return_value=False)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    with pytest.raises(HomeAssistantError):
        await ent.async_start()
    with pytest.raises(HomeAssistantError):
        await ent.async_stop()
    with pytest.raises(HomeAssistantError):
        await ent.async_return_to_base()
    with pytest.raises(HomeAssistantError):
        await ent.async_set_fan_speed("Wall")


async def test_commands_no_data_raises(hass: HomeAssistant) -> None:
    """Test commands no data raises."""
    coord, _, _ = _coord(hass)
    coord.async_send_command = AsyncMock(return_value=True)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    ent._data = None
    with pytest.raises(HomeAssistantError):
        await ent.async_start()
    coord.async_send_command.assert_not_awaited()


async def test_set_fan_speed_invalid_raises(hass: HomeAssistant) -> None:
    """An unsupported fan speed raises a validation error and sends nothing."""
    coord, _, _ = _coord(hass)
    coord.async_send_command = AsyncMock(return_value=True)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    with pytest.raises(ServiceValidationError):
        await ent.async_set_fan_speed("NotAMode")
    coord.async_send_command.assert_not_awaited()


async def test_handle_coordinator_update_updates_data(hass: HomeAssistant) -> None:
    """A coordinator update refreshes the entity data and writes state."""
    coord, _, group = _coord(
        hass, device_dps={"0": dp(CleaningStatus, id=0, type=4, len=1, data="03")}
    )
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    await add_entity(hass, ent, domain="vacuum")
    ent._handle_coordinator_update()
    assert ent._data is group
    state = hass.states.get(ent.entity_id)
    assert state is not None
    assert state.state == VacuumActivity.CLEANING


async def test_handle_coordinator_update_idx_missing(hass: HomeAssistant) -> None:
    """Test handle coordinator update idx missing."""
    coord, _, group = _coord(hass)
    ent = WyBotVacuum(idx=IDX, coordinator=coord)
    await add_entity(hass, ent, domain="vacuum")
    coord.data = {}
    ent._handle_coordinator_update()
    # _data retained; battery None branch (no dps) also exercised.
    assert ent._data is group

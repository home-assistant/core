"""Tests for Vallox sensor platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

FILTER_SENSOR_ENTITY_ID = "sensor.vallox_remaining_time_for_filter"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_vallox_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities."""
    with patch("homeassistant.components.vallox.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_vallox_client")
@pytest.mark.parametrize(
    ("metrics", "time_zone", "expected_state"),
    [
        # metrics.json has the filter changed on 2024-02-16 with a 120 day interval
        pytest.param({}, "UTC", "2024-06-15T13:00:00+00:00", id="utc"),
        pytest.param({}, "Europe/Helsinki", "2024-06-15T10:00:00+00:00", id="helsinki"),
        pytest.param(
            {}, "America/New_York", "2024-06-15T17:00:00+00:00", id="new_york"
        ),
        pytest.param(
            {"A_CYC_FILTER_CHANGE_INTERVAL": 0},
            "UTC",
            "2024-02-16T13:00:00+00:00",
            id="no_interval_days",
        ),
        pytest.param(
            {"A_CYC_FILTER_CHANGE_INTERVAL": None},
            "UTC",
            STATE_UNKNOWN,
            id="interval_missing",
        ),
    ],
)
async def test_remaining_time_for_filter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    time_zone: str,
    expected_state: str,
) -> None:
    """Test the remaining time for filter sensor."""
    await hass.config.async_set_time_zone(time_zone)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FILTER_SENSOR_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        pytest.param({"A_CYC_STATE": 1}, "Away", id="away"),
        pytest.param({"A_CYC_BOOST_TIMER": 30}, "Boost", id="boost"),
        pytest.param({"A_CYC_STATE": 3}, STATE_UNKNOWN, id="unknown_profile"),
    ],
)
async def test_current_profile_sensor(hass: HomeAssistant, expected_state: str) -> None:
    """Test the current profile sensor."""
    state = hass.states.get("sensor.vallox_current_profile")
    assert state
    assert state.state == expected_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_states"),
    [
        # The fan speeds come from metrics.json: 30%, 1310 rpm and 1270 rpm.
        pytest.param({"A_CYC_MODE": 0}, ("30", "1310", "1270"), id="fan_on"),
        # The unit keeps reporting its last fan speeds after it is turned off.
        pytest.param({"A_CYC_MODE": 5}, ("0", "0", "0"), id="fan_off"),
    ],
)
async def test_fan_speed_sensors(
    hass: HomeAssistant, expected_states: tuple[str, str, str]
) -> None:
    """Test that the fan speed sensors report 0 while the unit is off."""
    states = tuple(
        hass.states.get(entity_id).state
        for entity_id in (
            "sensor.vallox_fan_speed",
            "sensor.vallox_extract_fan_speed",
            "sensor.vallox_supply_fan_speed",
        )
    )
    assert states == expected_states


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        pytest.param({"A_CYC_CELL_STATE": 0}, "Heat Recovery", id="heat_recovery"),
        pytest.param({"A_CYC_CELL_STATE": 1}, "Cool Recovery", id="cool_recovery"),
        pytest.param({"A_CYC_CELL_STATE": 2}, "Bypass", id="bypass"),
        pytest.param({"A_CYC_CELL_STATE": 3}, "Defrosting", id="defrosting"),
        pytest.param({"A_CYC_CELL_STATE": 4}, STATE_UNKNOWN, id="unknown_value"),
        pytest.param({"A_CYC_CELL_STATE": None}, STATE_UNKNOWN, id="missing"),
    ],
)
async def test_cell_state_sensor(hass: HomeAssistant, expected_state: str) -> None:
    """Test cell state sensor in different states."""
    state = hass.states.get("sensor.vallox_cell_state")
    assert state
    assert state.state == expected_state


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        pytest.param({"A_CYC_STATE": 0}, STATE_UNKNOWN, id="home"),
        pytest.param({"A_CYC_STATE": 1}, STATE_UNKNOWN, id="away"),
        pytest.param({"A_CYC_EXTRA_TIMER": 10}, "10", id="extra"),
        pytest.param({"A_CYC_FIREPLACE_TIMER": 9}, "9", id="fireplace"),
        pytest.param({"A_CYC_BOOST_TIMER": 8}, "8", id="boost"),
    ],
)
async def test_profile_duration_sensor(
    hass: HomeAssistant, expected_state: str
) -> None:
    """Test profile duration sensor in different profiles."""
    state = hass.states.get("sensor.vallox_profile_duration")
    assert state
    assert state.state == expected_state

"""Tests for ZoneMinder sensor entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from zoneminder.monitor import MonitorState, TimePeriod

from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import create_mock_monitor

from tests.common import async_fire_time_changed


async def _setup_zm_with_sensors(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    zm_config: dict,
    monitors: list,
    freezer: FrozenDateTimeFactory,
    sensor_config: dict | None = None,
    is_available: bool = True,
    active_state: str | None = "Running",
) -> None:
    """Set up ZM component with sensor platform and trigger first poll."""
    mock_zoneminder_client.get_monitors.return_value = monitors
    type(mock_zoneminder_client).is_available = PropertyMock(return_value=is_available)
    mock_zoneminder_client.get_active_state.return_value = active_state

    assert await async_setup_component(hass, DOMAIN, zm_config)
    await hass.async_block_till_done(wait_background_tasks=True)

    if sensor_config is None:
        sensor_config = {
            "sensor": [
                {
                    "platform": DOMAIN,
                    "monitored_conditions": [
                        "all",
                        "hour",
                        "day",
                        "week",
                        "month",
                    ],
                }
            ]
        }
    assert await async_setup_component(hass, "sensor", sensor_config)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Trigger first poll to update entity state
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


# --- Monitor Status Sensor ---


async def test_monitor_status_sensor_exists(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test monitor status sensor is created."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await _setup_zm_with_sensors(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("sensor.front_door_status")
    assert state is not None


async def test_monitor_status_sensor_value(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test monitor status sensor shows MonitorState value."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.RECORD)]
    await _setup_zm_with_sensors(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("sensor.front_door_status")
    assert state is not None
    assert state.state == "Record"


@pytest.mark.parametrize(
    ("monitor_state", "expected_value"),
    [
        (MonitorState.NONE, "None"),
        (MonitorState.MONITOR, "Monitor"),
        (MonitorState.MODECT, "Modect"),
        (MonitorState.RECORD, "Record"),
        (MonitorState.MOCORD, "Mocord"),
        (MonitorState.NODECT, "Nodect"),
    ],
)
async def test_monitor_status_sensor_all_states(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
    monitor_state: MonitorState,
    expected_value: str,
) -> None:
    """Test monitor status sensor with all MonitorState values."""
    monitors = [create_mock_monitor(name="Cam", function=monitor_state)]
    await _setup_zm_with_sensors(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("sensor.cam_status")
    assert state is not None
    assert state.state == expected_value


async def test_monitor_status_sensor_unavailable(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test monitor status sensor when monitor is unavailable."""
    monitors = [
        create_mock_monitor(name="Front Door", is_available=False, function=None)
    ]
    await _setup_zm_with_sensors(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("sensor.front_door_status")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_monitor_status_sensor_null_function(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test monitor status sensor when function is falsy."""
    monitors = [
        create_mock_monitor(name="Front Door", function=None, is_available=True)
    ]
    await _setup_zm_with_sensors(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("sensor.front_door_status")
    assert state is not None


# --- Event Sensors ---


@pytest.mark.parametrize(
    ("condition", "expected_name_suffix", "expected_value"),
    [
        ("all", "Events", "100"),
        ("hour", "Events Last Hour", "5"),
        ("day", "Events Last Day", "20"),
        ("week", "Events Last Week", "50"),
        ("month", "Events Last Month", "80"),
    ],
)
async def test_event_sensor_for_each_time_period(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
    condition: str,
    expected_name_suffix: str,
    expected_value: str,
) -> None:
    """Test event sensors for all 5 time periods."""
    monitors = [create_mock_monitor(name="Front Door")]
    sensor_config = {
        "sensor": [
            {
                "platform": DOMAIN,
                "monitored_conditions": [condition],
            }
        ]
    }
    await _setup_zm_with_sensors(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        sensor_config=sensor_config,
    )

    entity_id = f"sensor.front_door_{expected_name_suffix.lower().replace(' ', '_')}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_value


async def test_event_sensor_unit_of_measurement(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event sensors have 'Events' unit of measurement."""
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_sensors(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("sensor.front_door_events")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == "Events"


async def test_event_sensor_name_format(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event sensor name format is '{monitor_name} {time_period_title}'."""
    monitors = [create_mock_monitor(name="Back Yard")]
    sensor_config = {
        "sensor": [
            {
                "platform": DOMAIN,
                "monitored_conditions": ["hour"],
            }
        ]
    }
    await _setup_zm_with_sensors(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        sensor_config=sensor_config,
    )

    state = hass.states.get("sensor.back_yard_events_last_hour")
    assert state is not None
    assert state.name == "Back Yard Events Last Hour"


async def test_event_sensor_none_handling(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test event sensor handles None event count."""
    monitors = [
        create_mock_monitor(
            name="Front Door",
            events=dict.fromkeys(TimePeriod),
        )
    ]
    await _setup_zm_with_sensors(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("sensor.front_door_events")
    assert state is not None


# --- Run State Sensor ---


async def test_run_state_sensor_exists(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test run state sensor is created."""
    monitors = [create_mock_monitor(name="Cam")]
    await _setup_zm_with_sensors(
        hass, mock_zoneminder_client, single_server_config, monitors, freezer
    )

    state = hass.states.get("sensor.run_state")
    assert state is not None


async def test_run_state_sensor_value(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test run state sensor shows state name."""
    monitors = [create_mock_monitor(name="Cam")]
    await _setup_zm_with_sensors(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        active_state="Home",
    )

    state = hass.states.get("sensor.run_state")
    assert state is not None
    assert state.state == "Home"


async def test_run_state_sensor_unavailable(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test run state sensor when server unavailable."""
    monitors = [create_mock_monitor(name="Cam")]
    await _setup_zm_with_sensors(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        is_available=False,
        active_state=None,
    )

    state = hass.states.get("sensor.run_state")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


# --- Platform behavior ---


async def test_platform_not_ready_empty_monitors(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test PlatformNotReady on empty monitors."""
    mock_zoneminder_client.get_monitors.return_value = []

    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()
    await async_setup_component(
        hass,
        "sensor",
        {"sensor": [{"platform": DOMAIN}]},
    )
    await hass.async_block_till_done()

    # No sensor entities should exist (PlatformNotReady caught by HA)
    states = hass.states.async_all("sensor")
    assert len(states) == 0


async def test_subset_condition_filtering(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test only selected monitored_conditions get event sensors."""
    monitors = [create_mock_monitor(name="Cam")]
    sensor_config = {
        "sensor": [
            {
                "platform": DOMAIN,
                "monitored_conditions": ["hour", "day"],
            }
        ]
    }
    await _setup_zm_with_sensors(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        sensor_config=sensor_config,
    )

    # Should have: 1 status + 2 event + 1 run state = 4 sensors
    states = hass.states.async_all("sensor")
    assert len(states) == 4

    # These should exist
    assert hass.states.get("sensor.cam_events_last_hour") is not None
    assert hass.states.get("sensor.cam_events_last_day") is not None

    # These should NOT exist
    assert hass.states.get("sensor.cam_events") is None
    assert hass.states.get("sensor.cam_events_last_week") is None
    assert hass.states.get("sensor.cam_events_last_month") is None


async def test_default_conditions_only_all(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test default monitored_conditions is only 'all'."""
    monitors = [create_mock_monitor(name="Cam")]
    sensor_config = {"sensor": [{"platform": DOMAIN}]}
    await _setup_zm_with_sensors(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        sensor_config=sensor_config,
    )

    # Should have: 1 status + 1 event (all) + 1 run state = 3 sensors
    states = hass.states.async_all("sensor")
    assert len(states) == 3


async def test_include_archived_flag(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test include_archived flag is passed correctly to get_events."""
    monitors = [create_mock_monitor(name="Cam")]
    sensor_config = {
        "sensor": [
            {
                "platform": DOMAIN,
                "include_archived": True,
                "monitored_conditions": ["all"],
            }
        ]
    }
    await _setup_zm_with_sensors(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        sensor_config=sensor_config,
    )

    # Verify get_events was called with include_archived=True
    monitors[0].get_events.assert_called_with(TimePeriod.ALL, True)


async def test_sensor_count_calculation(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test correct number of sensors created per monitor and client.

    For each monitor: 1 status + N event sensors
    Plus: 1 run state sensor per client
    """
    monitors = [
        create_mock_monitor(monitor_id=1, name="Cam1"),
        create_mock_monitor(monitor_id=2, name="Cam2"),
    ]
    sensor_config = {
        "sensor": [
            {
                "platform": DOMAIN,
                "monitored_conditions": ["all", "hour"],
                "include_archived": False,
            }
        ]
    }
    await _setup_zm_with_sensors(
        hass,
        mock_zoneminder_client,
        single_server_config,
        monitors,
        freezer,
        sensor_config=sensor_config,
    )

    # 2 monitors * (1 status + 2 events) + 1 run state = 7
    assert len(hass.states.async_all("sensor")) == 7

"""Tests for ZoneMinder sensor entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from zoneminder.monitor import Monitor, MonitorState, TimePeriod

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.components.zoneminder.sensor import setup_platform
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MOCK_HOST, create_mock_monitor, create_mock_zm_client

from tests.common import async_fire_time_changed


async def _setup_zm_with_sensors(
    hass: HomeAssistant,
    zm_config: dict,
    monitors: list,
    sensor_config: dict | None = None,
    is_available: bool = True,
    active_state: str | None = "Running",
) -> MagicMock:
    """Set up ZM component with sensor platform and trigger first poll."""
    client = create_mock_zm_client(
        monitors=monitors, is_available=is_available, active_state=active_state
    )

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        return_value=client,
    ):
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
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=60), fire_all=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    return client


# --- Monitor Status Sensor ---


async def test_monitor_status_sensor_exists(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test monitor status sensor is created."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

    state = hass.states.get("sensor.front_door_status")
    assert state is not None


async def test_monitor_status_sensor_value(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test monitor status sensor shows MonitorState value."""
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.RECORD)]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

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
    single_server_config,
    monitor_state: MonitorState,
    expected_value: str,
) -> None:
    """Test monitor status sensor with all MonitorState values."""
    monitors = [create_mock_monitor(name="Cam", function=monitor_state)]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

    state = hass.states.get("sensor.cam_status")
    assert state is not None
    assert state.state == expected_value


async def test_monitor_status_sensor_unavailable(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test monitor status sensor when monitor is unavailable."""
    monitors = [
        create_mock_monitor(name="Front Door", is_available=False, function=None)
    ]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

    state = hass.states.get("sensor.front_door_status")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_monitor_status_sensor_null_function(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test monitor status sensor when function is falsy."""
    monitors = [
        create_mock_monitor(name="Front Door", function=None, is_available=True)
    ]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

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
    single_server_config,
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
        hass, single_server_config, monitors, sensor_config=sensor_config
    )

    entity_id = f"sensor.front_door_{expected_name_suffix.lower().replace(' ', '_')}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_value


async def test_event_sensor_unit_of_measurement(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test event sensors have 'Events' unit of measurement."""
    monitors = [create_mock_monitor(name="Front Door")]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

    state = hass.states.get("sensor.front_door_events")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == "Events"


async def test_event_sensor_name_format(
    hass: HomeAssistant, single_server_config
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
        hass, single_server_config, monitors, sensor_config=sensor_config
    )

    state = hass.states.get("sensor.back_yard_events_last_hour")
    assert state is not None
    assert state.name == "Back Yard Events Last Hour"


async def test_event_sensor_none_handling(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test event sensor handles None event count."""
    monitors = [
        create_mock_monitor(
            name="Front Door",
            events=dict.fromkeys(TimePeriod),
        )
    ]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

    state = hass.states.get("sensor.front_door_events")
    assert state is not None


# --- Run State Sensor ---


async def test_run_state_sensor_exists(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test run state sensor is created."""
    monitors = [create_mock_monitor(name="Cam")]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

    state = hass.states.get("sensor.run_state")
    assert state is not None


async def test_run_state_sensor_value(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test run state sensor shows state name."""
    monitors = [create_mock_monitor(name="Cam")]
    await _setup_zm_with_sensors(
        hass, single_server_config, monitors, active_state="Home"
    )

    state = hass.states.get("sensor.run_state")
    assert state is not None
    assert state.state == "Home"


async def test_run_state_sensor_unavailable(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test run state sensor when server unavailable."""
    monitors = [create_mock_monitor(name="Cam")]
    await _setup_zm_with_sensors(
        hass,
        single_server_config,
        monitors,
        is_available=False,
        active_state=None,
    )

    state = hass.states.get("sensor.run_state")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


# --- Platform behavior ---


async def test_platform_not_ready_empty_monitors(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test PlatformNotReady on empty monitors."""
    client = create_mock_zm_client(monitors=[])

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        return_value=client,
    ):
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
    hass: HomeAssistant, single_server_config
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
        hass, single_server_config, monitors, sensor_config=sensor_config
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
    hass: HomeAssistant, single_server_config
) -> None:
    """Test default monitored_conditions is only 'all'."""
    monitors = [create_mock_monitor(name="Cam")]
    sensor_config = {"sensor": [{"platform": DOMAIN}]}
    await _setup_zm_with_sensors(
        hass, single_server_config, monitors, sensor_config=sensor_config
    )

    # Should have: 1 status + 1 event (all) + 1 run state = 3 sensors
    states = hass.states.async_all("sensor")
    assert len(states) == 3


async def test_include_archived_flag(hass: HomeAssistant, single_server_config) -> None:
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
        hass, single_server_config, monitors, sensor_config=sensor_config
    )

    # Verify get_events was called with include_archived=True
    monitors[0].get_events.assert_called_with(TimePeriod.ALL, True)


def test_sensor_count_calculation(hass: HomeAssistant) -> None:
    """Test correct number of sensors created per monitor and client.

    For each monitor: 1 status + N event sensors
    Plus: 1 run state sensor per client
    """
    monitors = [
        create_mock_monitor(monitor_id=1, name="Cam1"),
        create_mock_monitor(monitor_id=2, name="Cam2"),
    ]
    client = create_mock_zm_client(monitors=monitors)
    hass.data[DOMAIN] = {MOCK_HOST: client}

    entities: list[SensorEntity] = []
    mock_add = MagicMock(side_effect=entities.extend)

    config = {
        "monitored_conditions": ["all", "hour"],
        "include_archived": False,
    }
    setup_platform(hass, config, mock_add)

    # 2 monitors * (1 status + 2 events) + 1 run state = 7
    assert len(entities) == 7


@pytest.mark.xfail(reason="BUG-05: No unique_id on any entity")
async def test_sensor_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, single_server_config
) -> None:
    """Sensor entities should have unique_id for UI customization.

    No entity in the integration sets unique_id. This means entities cannot
    be customized via the HA UI and are fragile to name changes.
    """
    monitors = [create_mock_monitor(name="Front Door", function=MonitorState.MODECT)]
    await _setup_zm_with_sensors(hass, single_server_config, monitors)

    entry = entity_registry.async_get("sensor.front_door_status")
    assert entry is not None
    assert entry.unique_id is not None


@pytest.mark.xfail(
    reason="BUG-03: monitor.function getter makes HTTP call on every read"
)
async def test_function_property_no_side_effects(
    hass: HomeAssistant, single_server_config
) -> None:
    """Reading monitor.function should not trigger an HTTP request.

    The zm-py Monitor.function property calls update_monitor() on every read,
    which makes an HTTP GET to monitors/{id}.json. HA reads function from both
    sensor.py and switch.py, so the same data is fetched multiple times.
    """
    # Create a stub client that tracks calls to get_state
    stub_client = MagicMock()
    stub_client.get_state.return_value = {
        "monitor": {
            "Monitor": {"Function": "Modect"},
            "Monitor_Status": {"CaptureFPS": "15.00"},
        }
    }
    stub_client.verify_ssl = True

    raw_result = {
        "Monitor": {
            "Id": "1",
            "Name": "Test",
            "Controllable": "0",
            "StreamReplayBuffer": "0",
            "ServerId": "0",
        },
        "Monitor_Status": {"CaptureFPS": "15.00"},
    }
    stub_client.get_zms_url_for_monitor.return_value = "http://example.com/zms"
    stub_client.get_url_with_auth.return_value = "http://example.com/zms?auth=1"

    monitor = Monitor(stub_client, raw_result)
    stub_client.get_state.reset_mock()

    # Reading function should NOT make an HTTP call
    _ = monitor.function
    assert stub_client.get_state.call_count == 0

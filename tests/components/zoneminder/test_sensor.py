"""Tests for ZoneMinder sensor entities."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, PropertyMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from zoneminder.monitor import MonitorState, TimePeriod

from homeassistant.components.zoneminder.const import CONF_INCLUDE_ARCHIVED, DOMAIN
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import MOCK_CONFIG_DATA, MOCK_OPTIONS, create_mock_monitor

STATUS_ENTITY_ID = "sensor.front_door_status"
RUN_STATE_ENTITY_ID = "sensor.run_state"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an entity update poll."""
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("mock_zoneminder_client", "entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor entities."""
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])
    await _poll(hass, freezer)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("data", "expected_enabled"),
    [
        pytest.param(
            MOCK_CONFIG_DATA,
            {STATUS_ENTITY_ID, "sensor.front_door_events"},
            id="default",
        ),
        pytest.param(
            {**MOCK_CONFIG_DATA, CONF_MONITORED_CONDITIONS: ["hour", "week"]},
            {
                STATUS_ENTITY_ID,
                "sensor.front_door_events_last_hour",
                "sensor.front_door_events_last_week",
            },
            id="imported_monitored_conditions",
        ),
    ],
)
@pytest.mark.usefixtures("mock_zoneminder_client")
async def test_event_sensors_enabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    data: dict[str, Any],
    expected_enabled: set[str],
) -> None:
    """Test which event sensors are enabled by default."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=MOCK_OPTIONS)
    await setup_integration(hass, entry, [Platform.SENSOR])

    enabled = {
        entity_entry.entity_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if entity_entry.entity_id.startswith("sensor.front_door_")
        and not entity_entry.disabled
    }
    assert enabled == expected_enabled


@pytest.mark.parametrize(
    ("function", "is_available", "expected"),
    [
        *(
            pytest.param(state, True, state.value, id=state.value)
            for state in MonitorState
        ),
        pytest.param(None, True, STATE_UNKNOWN, id="no_function"),
        pytest.param(None, False, STATE_UNAVAILABLE, id="unavailable"),
    ],
)
async def test_monitor_status(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    function: MonitorState | None,
    is_available: bool,
    expected: str,
) -> None:
    """Test the monitor status sensor shows the monitor function."""
    mock_zoneminder_client.get_monitors.return_value = [
        create_mock_monitor(function=function, is_available=is_available)
    ]
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])
    await _poll(hass, freezer)

    assert (state := hass.states.get(STATUS_ENTITY_ID))
    assert state.state == expected


async def test_monitor_status_follows_server_change(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the monitor status sensor refreshes the monitor on each poll."""
    monitor = create_mock_monitor(function=MonitorState.MONITOR)
    mock_zoneminder_client.get_monitors.return_value = [monitor]
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])
    await _poll(hass, freezer)
    assert (state := hass.states.get(STATUS_ENTITY_ID))
    assert state.state == "Monitor"

    def change_on_server() -> None:
        monitor.function = MonitorState.RECORD

    # zm-py only fetches new monitor data in update_monitor
    monitor.update_monitor.side_effect = change_on_server
    await _poll(hass, freezer)

    assert (state := hass.states.get(STATUS_ENTITY_ID))
    assert state.state == "Record"


async def test_event_sensor_none_value(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the event sensor is unknown when no event count is returned."""
    mock_zoneminder_client.get_monitors.return_value = [
        create_mock_monitor(events={TimePeriod.ALL: None})
    ]
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])
    await _poll(hass, freezer)

    assert (state := hass.states.get("sensor.front_door_events"))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("include_archived", [True, False])
async def test_include_archived_option(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    include_archived: bool,
) -> None:
    """Test the include_archived option is passed to get_events."""
    monitor = create_mock_monitor()
    mock_zoneminder_client.get_monitors.return_value = [monitor]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options={**MOCK_OPTIONS, CONF_INCLUDE_ARCHIVED: include_archived},
    )
    await setup_integration(hass, entry, [Platform.SENSOR])
    await _poll(hass, freezer)

    monitor.get_events.assert_called_with(TimePeriod.ALL, include_archived)


async def test_run_state_unavailable(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the run state sensor is unavailable when the server is."""
    type(mock_zoneminder_client).is_available = PropertyMock(return_value=False)
    await setup_integration(hass, mock_config_entry, [Platform.SENSOR])
    await _poll(hass, freezer)

    assert (state := hass.states.get(RUN_STATE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

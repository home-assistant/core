"""Tests for the eGauge data coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock

from egauge_async.json.client import EgaugeAuthenticationError
from freezegun.api import FrozenDateTimeFactory
from httpx import ConnectError
import pytest

from homeassistant.components.egauge.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time("2025-01-15T10:00:00+00:00")
async def test_coordinator_initial_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test coordinator fetches static and dynamic data on first refresh."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify static device info was fetched
    assert mock_egauge_client.get_device_serial_number.called
    assert mock_egauge_client.get_hostname.called
    assert mock_egauge_client.get_register_info.called

    # Verify dynamic data was fetched
    assert mock_egauge_client.get_current_measurements.called
    assert mock_egauge_client.get_current_counters.called

    # Verify coordinator has data
    coordinator = mock_config_entry.runtime_data
    assert coordinator.serial_number == "ABC123456"
    assert coordinator.hostname == "egauge-home"
    assert coordinator.data is not None
    assert "Grid" in coordinator.data.measurements
    assert "Grid" in coordinator.data.counters


@pytest.mark.freeze_time("2025-01-15T10:00:00+00:00")
async def test_coordinator_periodic_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test coordinator periodic data updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initial state
    state = hass.states.get("sensor.egauge_home_grid")
    assert state.state == "1500.0"

    # Update mock data
    mock_egauge_client.get_current_measurements.return_value = {
        "Grid": 2000.0,
        "Solar": -3000.0,
        "Temp": 45.0,
    }
    mock_egauge_client.get_current_counters.return_value = {
        "Grid": 900000000.0,  # 250 kWh
        "Solar": 630000000.0,  # 175 kWh
        "Temp": 0.0,
    }

    # Trigger coordinator update (30 second interval)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify sensors reflect new data
    state = hass.states.get("sensor.egauge_home_grid")
    assert state.state == "2000.0"

    state = hass.states.get("sensor.egauge_home_grid_energy")
    assert state.state == "250.0"

    state = hass.states.get("sensor.egauge_home_solar")
    assert state.state == "-3000.0"


@pytest.mark.freeze_time("2025-01-15T10:00:00+00:00")
async def test_coordinator_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test coordinator handles authentication errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initial state
    state = hass.states.get("sensor.egauge_home_grid")
    assert state is not None
    assert state.state == "1500.0"

    # Trigger auth error on next update
    mock_egauge_client.get_current_measurements.side_effect = EgaugeAuthenticationError

    # Trigger coordinator update
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify entities become unavailable
    state = hass.states.get("sensor.egauge_home_grid")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Verify config entry shows auth failed (triggers reauth flow)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


@pytest.mark.freeze_time("2025-01-15T10:00:00+00:00")
async def test_coordinator_connection_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test coordinator handles connection errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initial state
    state = hass.states.get("sensor.egauge_home_grid")
    assert state is not None
    assert state.state == "1500.0"

    # Trigger connection error on next update
    mock_egauge_client.get_current_measurements.side_effect = ConnectError(
        "Connection failed"
    )

    # Trigger coordinator update
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify entities become unavailable
    state = hass.states.get("sensor.egauge_home_grid")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Restore connection
    mock_egauge_client.get_current_measurements.side_effect = None
    mock_egauge_client.get_current_measurements.return_value = {
        "Grid": 1500.0,
        "Solar": -2500.0,
        "Temp": 45.0,
    }

    # Trigger coordinator update
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify entities recover
    state = hass.states.get("sensor.egauge_home_grid")
    assert state is not None
    assert state.state == "1500.0"

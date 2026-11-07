"""Tests for the eGauge sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from egauge_async.exceptions import EgaugeParsingException
from freezegun.api import FrozenDateTimeFactory
from httpx2 import ConnectError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.egauge.const import CONF_INVERT_REGISTERS, DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify main device created with hostname
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ABC123456"), mock_config_entry.entry_id
    )
    assert device_entry
    assert device_entry == snapshot


async def test_inverted_register_reports_the_opposite_sign(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only power sensors of an inverted register flip sign."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_INVERT_REGISTERS: ["Grid"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    def state_for(register: str, key: str) -> str | None:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"ABC123456_{register}_{key}"
        )
        return hass.states.get(entity_id).state if entity_id else None

    assert state_for("Grid", "power") == "-1500.0"
    # Energy stays as the meter reports it: a negated total-increasing sensor
    # is rejected by the recorder, so energy inversion is not offered.
    assert state_for("Grid", "energy") == "125.0"
    # The register beside it, and a register of another type, are untouched.
    assert state_for("Solar", "power") == "-2500.0"
    assert state_for("L1", "voltage") == "123.4"
    assert state_for("S1", "current") == "1.2"


@pytest.mark.parametrize(
    "exception", [EgaugeParsingException, ConnectError("Connection failed")]
)
@pytest.mark.freeze_time("2025-01-15T10:00:00+00:00")
async def test_sensor_error(
    hass: HomeAssistant,
    mock_egauge_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test errors that occur after setup are handled."""

    # Trigger exception on next update
    mock_egauge_client.get_current_measurements.side_effect = exception

    # Trigger update
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Test Grid power sensor
    state = hass.states.get("sensor.egauge_home_grid_power")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Test Grid energy sensor
    state = hass.states.get("sensor.egauge_home_grid_energy")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Clear exception
    mock_egauge_client.get_current_measurements.side_effect = None

    # Trigger update
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Test Grid power sensor is available
    state = hass.states.get("sensor.egauge_home_grid_power")
    assert state
    assert state.state == "1500.0"

    # Test Grid energy sensor is available
    state = hass.states.get("sensor.egauge_home_grid_energy")
    assert state
    assert state.state == "125.0"


@pytest.mark.freeze_time("2025-01-15T10:00:00+00:00")
async def test_register_removed(
    hass: HomeAssistant,
    mock_egauge_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test case where a register is removed on the eGauge device."""

    # Remove "Grid" register
    original_measurements = await mock_egauge_client.get_current_measurements()
    original_counters = await mock_egauge_client.get_current_counters()
    new_measurements = {k: v for k, v in original_measurements.items() if k != "Grid"}
    new_counters = {k: v for k, v in original_counters.items() if k != "Grid"}
    mock_egauge_client.get_current_measurements.return_value = new_measurements
    mock_egauge_client.get_current_counters.return_value = new_counters

    # Trigger update
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Test Grid power sensor
    state = hass.states.get("sensor.egauge_home_grid_power")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Test Grid energy sensor
    state = hass.states.get("sensor.egauge_home_grid_energy")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Test that other sensors still work
    state = hass.states.get("sensor.egauge_home_solar_power")
    assert state
    assert state.state == "-2500.0"

    state = hass.states.get("sensor.egauge_home_solar_energy")
    assert state
    assert state.state == "87.5"

    # Restore "Grid" register
    mock_egauge_client.get_current_measurements.return_value = original_measurements
    mock_egauge_client.get_current_counters.return_value = original_counters

    # Trigger update
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Test Grid power sensor is available
    state = hass.states.get("sensor.egauge_home_grid_power")
    assert state
    assert state.state == "1500.0"

    # Test Grid energy sensor is available
    state = hass.states.get("sensor.egauge_home_grid_energy")
    assert state
    assert state.state == "125.0"

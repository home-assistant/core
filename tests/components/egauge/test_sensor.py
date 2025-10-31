"""Tests for the eGauge sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from egauge_async.exceptions import EgaugeAuthenticationError
from freezegun.api import FrozenDateTimeFactory
from httpx import ConnectError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.egauge.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

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

    # Verify device created with hostname
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "ABC123456")})
    assert device_entry
    assert device_entry == snapshot


@pytest.mark.parametrize(
    "exception", [EgaugeAuthenticationError, ConnectError("Connection failed")]
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

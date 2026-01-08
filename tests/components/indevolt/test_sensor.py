"""Tests for the Indevolt sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.indevolt.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("generation", [2, 1], indirect=True)
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor registration for sensors."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_sensor_availability(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensor availability / non-availability."""
    with patch("homeassistant.components.indevolt.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("sensor.indevolt_cms_sf2000_battery_soc"))
    assert state.state == "92.0"

    mock_indevolt.fetch_data.side_effect = ConnectionError
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=SCAN_INTERVAL))
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.indevolt_cms_sf2000_battery_soc"))
    assert state.state == STATE_UNAVAILABLE

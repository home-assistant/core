"""Test the Imeon Inverter sensors."""

from unittest.mock import MagicMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imeon_inverter.coordinator import INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Imeon Inverter sensors."""
    with patch("homeassistant.components.imeon_inverter.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError,
        ClientError,
        ValueError,
    ],
)
@pytest.mark.asyncio
async def test_sensor_unavailable_on_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imeon_inverter: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that sensor becomes unavailable when update raises an error."""
    entity_id = "sensor.imeon_inverter_battery_power"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    mock_imeon_inverter.update.side_effect = exception

    freezer.tick(INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_imeon_inverter.update.side_effect = None

    freezer.tick(INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

"""Tests for the Aladdin Connect sensor platform."""

from unittest.mock import AsyncMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.test_door_battery"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up integration with only the sensor platform."""
    with patch("homeassistant.components.aladdin_connect.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, entry)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entity states and attributes."""
    await _setup(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable when coordinator update fails."""
    await _setup(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_aladdin_connect_api.update_door.side_effect = aiohttp.ClientError()
    freezer.tick(15)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

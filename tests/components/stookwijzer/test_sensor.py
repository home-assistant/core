"""Tests for the Stookwijzer sensor platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stookwijzer.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

WIND_SPEED_ENTITY_ID = "sensor.stookwijzer_wind_speed"


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Stookwijzer entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_entities_unavailable_on_failed_update(
    hass: HomeAssistant,
    mock_stookwijzer: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entities become unavailable when the client fails to update."""
    client = mock_stookwijzer.return_value
    mock_async_update = client.async_update.side_effect

    # A failed request keeps the previous advice and last_updated in the client
    client.async_update.side_effect = None
    client.windspeed_ms = ""
    client.lki = ""

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WIND_SPEED_ENTITY_ID).state == STATE_UNAVAILABLE

    client.async_update.side_effect = mock_async_update
    client.windspeed_ms = 2.5
    client.lki = 2

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(WIND_SPEED_ENTITY_ID).state != STATE_UNAVAILABLE

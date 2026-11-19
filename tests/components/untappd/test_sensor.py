"""Test the Untappd sensors."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.untappd.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_untappd_client")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensors."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_checkins(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_untappd_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the last check-in sensors are unknown for an account without any."""
    await setup_integration(hass, mock_config_entry)
    mock_untappd_client.get_user_checkins.return_value = []
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id in (
        "sensor.hopsfan_last_check_in",
        "sensor.hopsfan_last_beer",
        "sensor.hopsfan_last_brewery",
        "sensor.hopsfan_last_rating",
    ):
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNKNOWN
        assert "entity_picture" not in state.attributes

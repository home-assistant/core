"""Tests for the Tedee Sensors."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiotedee import TedeeLock
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SENSORS = (
    "battery",
    "pullspring_duration",
)


async def test_sensors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test tedee sensors."""
    with patch("homeassistant.components.tedee.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_new_sensors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure sensors for new lock are added automatically."""

    for key in SENSORS:
        state = hass.states.get(f"sensor.lock_4e5f_{key}")
        assert state is None

    mock_tedee.locks_dict[666666] = TedeeLock("Lock-4E5F", 666666, 2)

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for key in SENSORS:
        state = hass.states.get(f"sensor.lock_4e5f_{key}")
        assert state

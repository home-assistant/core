"""Test the Fenecon Modbus sensor platform."""

from dataclasses import replace
from unittest.mock import MagicMock

from fenecon_modbus import FeneconConnectionError, FeneconData
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fenecon_modbus.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

GRID_POWER_ENTITY_ID = "sensor.fenecon_home_10_grid_power"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_fenecon_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_unavailable_and_recovery(
    hass: HomeAssistant,
    mock_fenecon_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable on a failed poll and recover."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(GRID_POWER_ENTITY_ID).state == "-830.0"

    mock_fenecon_client.read_data.side_effect = FeneconConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(GRID_POWER_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_fenecon_client.read_data.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(GRID_POWER_ENTITY_ID).state == "-830.0"


async def test_undefined_value(
    hass: HomeAssistant,
    mock_fenecon_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    data: FeneconData,
) -> None:
    """Test values the FEMS reports as undefined become unknown."""
    mock_fenecon_client.read_data.return_value = replace(
        data, grid_active_power=None, state=None
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(GRID_POWER_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get("sensor.fenecon_home_10_system_state").state == STATE_UNKNOWN

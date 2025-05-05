"""Tests for La Marzocco binary sensors."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.exceptions import RequestNotSuccessful
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco binary sensors."""

    with patch(
        "homeassistant.components.lamarzocco.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await async_init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.fixture(autouse=True)
def mock_websocket_terminated() -> Generator[bool]:
    """Mock websocket terminated."""
    with patch(
        "homeassistant.components.lamarzocco.coordinator.LaMarzoccoUpdateCoordinator.websocket_terminated",
        new=False,
    ) as mock_websocket_terminated:
        yield mock_websocket_terminated


async def test_brew_active_unavailable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco brew active becomes unavailable."""

    mock_lamarzocco.websocket.connected = False
    await async_init_integration(hass, mock_config_entry)
    state = hass.states.get(
        f"binary_sensor.{mock_lamarzocco.serial_number}_brewing_active"
    )
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_going_unavailable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor is going unavailable after an unsuccessful update."""
    brewing_active_sensor = (
        f"binary_sensor.{mock_lamarzocco.serial_number}_brewing_active"
    )
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get(brewing_active_sensor)
    assert state
    assert state.state != STATE_UNAVAILABLE

    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.get_dashboard.side_effect = RequestNotSuccessful("")
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(brewing_active_sensor)
    assert state
    assert state.state == STATE_UNAVAILABLE

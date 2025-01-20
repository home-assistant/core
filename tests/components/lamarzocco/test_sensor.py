"""Tests for La Marzocco sensors."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.const import MachineModel
from pylamarzocco.models import LaMarzoccoScale
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco sensors."""

    with patch("homeassistant.components.lamarzocco.PLATFORMS", [Platform.SENSOR]):
        await async_init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_shot_timer_not_exists(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_no_local_connection: MockConfigEntry,
) -> None:
    """Test the La Marzocco shot timer doesn't exist if host not set."""

    await async_init_integration(hass, mock_config_entry_no_local_connection)
    state = hass.states.get(f"sensor.{mock_lamarzocco.serial_number}_shot_timer")
    assert state is None


async def test_shot_timer_unavailable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco brew_active becomes unavailable."""

    mock_lamarzocco.websocket_connected = False
    await async_init_integration(hass, mock_config_entry)
    state = hass.states.get(f"sensor.{mock_lamarzocco.serial_number}_shot_timer")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", [MachineModel.LINEA_MINI])
async def test_no_steam_linea_mini(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure Linea Mini has no steam temp."""
    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number
    state = hass.states.get(f"sensor.{serial_number}_current_temp_steam")
    assert state is None


@pytest.mark.parametrize("device_fixture", [MachineModel.LINEA_MINI])
async def test_scale_battery(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the scale battery sensor."""
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.lmz_123a45_battery")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot


@pytest.mark.parametrize(
    "device_fixture",
    [MachineModel.GS3_AV, MachineModel.GS3_MP, MachineModel.LINEA_MICRA],
)
async def test_other_models_no_scale_battery(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure the other models don't have a battery sensor."""
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.lmz_123a45_battery")
    assert state is None


@pytest.mark.parametrize("device_fixture", [MachineModel.LINEA_MINI])
async def test_battery_on_new_scale_added(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure the battery sensor for a new scale is added automatically."""

    mock_lamarzocco.config.scale = None
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.lmz_123a45_battery")
    assert state is None

    mock_lamarzocco.config.scale = LaMarzoccoScale(
        connected=True, name="Scale-123A45", address="aa:bb:cc:dd:ee:ff", battery=50
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.scale_123a45_battery")
    assert state

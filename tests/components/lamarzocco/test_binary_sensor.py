"""Tests for La Marzocco binary sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.const import MachineModel
from pylamarzocco.exceptions import RequestNotSuccessful
from pylamarzocco.models import LaMarzoccoScale
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, async_fire_time_changed

BINARY_SENSORS = (
    "brewing_active",
    "backflush_active",
    "water_tank_empty",
)


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco binary sensors."""

    await async_init_integration(hass, mock_config_entry)

    serial_number = mock_lamarzocco.serial_number

    for binary_sensor in BINARY_SENSORS:
        state = hass.states.get(f"binary_sensor.{serial_number}_{binary_sensor}")
        assert state
        assert state == snapshot(name=f"{serial_number}_{binary_sensor}-binary_sensor")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry.device_id
        assert entry == snapshot(name=f"{serial_number}_{binary_sensor}-entry")


async def test_brew_active_does_not_exists(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_no_local_connection: MockConfigEntry,
) -> None:
    """Test the La Marzocco currently_making_coffee doesn't exist if host not set."""

    await async_init_integration(hass, mock_config_entry_no_local_connection)
    state = hass.states.get(f"sensor.{mock_lamarzocco.serial_number}_brewing_active")
    assert state is None


async def test_brew_active_unavailable(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco currently_making_coffee becomes unavailable."""

    mock_lamarzocco.websocket_connected = False
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

    mock_lamarzocco.get_config.side_effect = RequestNotSuccessful("")
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(brewing_active_sensor)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", [MachineModel.LINEA_MINI])
async def test_scale_connectivity(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the scale binary sensors."""
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.lmz_123a45_connectivity")
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
async def test_other_models_no_scale_connectivity(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure the other models don't have a connectivity sensor."""
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.lmz_123a45_connectivity")
    assert state is None


@pytest.mark.parametrize("device_fixture", [MachineModel.LINEA_MINI])
async def test_connectivity_on_new_scale_added(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure the connectivity binary sensor for a new scale is added automatically."""

    mock_lamarzocco.config.scale = None
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.scale_123a45_connectivity")
    assert state is None

    mock_lamarzocco.config.scale = LaMarzoccoScale(
        connected=True, name="Scale-123A45", address="aa:bb:cc:dd:ee:ff", battery=50
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.scale_123a45_connectivity")
    assert state

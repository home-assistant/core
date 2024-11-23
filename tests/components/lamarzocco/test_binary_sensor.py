"""Tests for La Marzocco binary sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.exceptions import RequestNotSuccessful
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

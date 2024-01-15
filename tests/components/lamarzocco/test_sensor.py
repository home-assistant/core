"""Tests for La Marzocco sensors."""
from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry

SENSORS = (
    "drink_statistics_coffee",
    "drink_statistics_coffee",
    "shot_timer",
    "current_coffee_temperature",
    "current_steam_temperature",
)


async def test_sensors(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco sensors."""

    serial_number = mock_lamarzocco.serial_number

    await async_init_integration(hass, mock_config_entry)

    for sensor in SENSORS:
        state = hass.states.get(f"sensor.{serial_number}_{sensor}")
        assert state
        assert state == snapshot(name=f"{serial_number}_{sensor}-sensor")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry.device_id
        assert entry == snapshot(name=f"{serial_number}_{sensor}-entry")


async def test_shot_timer_not_exists(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the La Marzocco shot timer doesn't exist if host not set."""

    data = mock_config_entry.data.copy()
    del data[CONF_HOST]
    hass.config_entries.async_update_entry(mock_config_entry, data=data)

    await async_init_integration(hass, mock_config_entry)
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

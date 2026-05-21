"""Tests for Swiss Hydrological Data sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import STATION_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_swiss_hydro_data: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot all Swiss Hydrological Data sensor entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_entities_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_swiss_hydro_data: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable on update failure."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.aare_bern_temperature")
    assert state is not None
    assert state.state == "5.2"

    mock_swiss_hydro_data.get_station.return_value = None

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.aare_bern_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_only_available_conditions_create_sensors(
    hass: HomeAssistant,
    mock_swiss_hydro_data: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test only sensors for available conditions are created."""
    data_without_discharge = {
        **STATION_DATA,
        "parameters": {
            k: v for k, v in STATION_DATA["parameters"].items() if k != "discharge"
        },
    }
    mock_swiss_hydro_data.get_station.return_value = data_without_discharge

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.aare_bern_temperature") is not None
    assert hass.states.get("sensor.aare_bern_level") is not None
    assert hass.states.get("sensor.aare_bern_discharge") is None

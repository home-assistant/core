"""Tests for the Vistapool binary_sensor platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vistapool.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform


@pytest.fixture(autouse=True)
def _only_binary_sensor_platform() -> Generator[None]:
    """Restrict integration setup to the binary_sensor platform for these tests."""
    with patch(
        "homeassistant.components.vistapool.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "fixture_name",
    [
        pytest.param("pool_data.json", id="default"),
        pytest.param("pool_data_all_modules.json", id="all_modules_enabled"),
    ],
)
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    fixture_name: str,
) -> None:
    """Test binary sensor entities for fixtures covering modules off and on."""
    mock_vistapool_client.fetch_pool_data.return_value = load_json_object_fixture(
        fixture_name, DOMAIN
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensors_hydrolysis_branch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the hydrolysis (non-electrolysis) branch creates the right entity."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasHidro": 1, "version": 1},
        "hidro": {"is_electrolysis": False, "low": 1},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_hydrolysis_low").state == STATE_ON
    assert hass.states.get("binary_sensor.my_pool_electrolysis_low") is None


async def test_binary_sensors_dosing_tank_low(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the dosing-tank sensor reports `on` when any installed tank is low."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasPH": 1, "version": 1},
        "modules": {"ph": {"tank": 1}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_dosing_tank").state == STATE_ON


async def test_binary_sensors_dosing_tank_unknown_when_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the dosing-tank sensor reports unknown when no tank values are available."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasPH": 1, "version": 1},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_dosing_tank").state == STATE_UNKNOWN


async def test_binary_sensors_string_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the Vistapool API's numeric-as-string values are coerced correctly."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"version": 1},
        "filtration": {"status": "1"},
        "backwash": {"status": "0"},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_filtration").state == STATE_ON
    assert hass.states.get("binary_sensor.my_pool_backwash").state == STATE_OFF


async def test_binary_sensors_string_has_flags(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test entity creation gates also coerce string has* flags."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasPH": "0", "hasRX": "1", "hasHidro": "0", "version": 1},
        "modules": {"rx": {"pump_status": 0, "tank": 0}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_redox_pump") is not None
    assert hass.states.get("binary_sensor.my_pool_ph_acid_pump") is None
    assert hass.states.get("binary_sensor.my_pool_hidro_flow") is None
    assert hass.states.get("binary_sensor.my_pool_electrolysis_low") is None
    assert hass.states.get("binary_sensor.my_pool_hydrolysis_low") is None


async def test_binary_sensors_fl2_requires_hidro(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test hidro_fl2 is not created when hasCL is set but hasHidro is not."""
    mock_vistapool_client.fetch_pool_data.return_value = {
        "main": {"hasCL": 1, "hasHidro": 0, "version": 1},
        "modules": {"cl": {"pump_status": 0, "tank": 0}},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.my_pool_hidro_fl2") is None
    assert hass.states.get("binary_sensor.my_pool_chlorine_pump") is not None


async def test_binary_sensors_multi_pool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test setup creates binary sensors for every pool on the account."""
    mock_vistapool_client.get_pools.return_value = {
        "pool_a": "Pool A",
        "pool_b": "Pool B",
    }
    mock_vistapool_client.fetch_pool_data.return_value = mock_pool_data
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.pool_a_filtration").state == STATE_ON
    assert hass.states.get("binary_sensor.pool_b_filtration").state == STATE_ON

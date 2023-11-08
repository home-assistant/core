"""Test the Nibe Heat Pump config flow."""
import asyncio
from typing import Any
from unittest.mock import patch

from nibe.coil import Coil, CoilData
from nibe.heatpump import Model
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import MockConnection, async_add_model


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.NUMBER]):
        yield


async def test_partial_refresh(
    hass: HomeAssistant,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that coordinator can handle partial fields."""
    coils[40031] = 10
    coils[40035] = None
    coils[40039] = 10

    await async_add_model(hass, Model.S320)

    data = hass.states.get("number.heating_offset_climate_system_1_40031")
    assert data == snapshot(name="1. Sensor is available")

    data = hass.states.get("number.min_supply_climate_system_1_40035")
    assert data == snapshot(name="2. Sensor is not available")

    data = hass.states.get("number.max_supply_climate_system_1_40035")
    assert data == snapshot(name="3. Sensor is available")


async def test_invalid_coil(
    hass: HomeAssistant,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
    freezer_ticker: Any,
) -> None:
    """That update coordinator correctly marks entities unavailable with missing coils."""
    entity_id = "number.heating_offset_climate_system_1_40031"
    coil_id = 40031

    coils[coil_id] = 10
    await async_add_model(hass, Model.S320)

    assert hass.states.get(entity_id) == snapshot(name="Sensor is available")

    coils.pop(coil_id)
    await freezer_ticker(60)

    assert hass.states.get(entity_id) == snapshot(name="Sensor is not available")


async def test_pushed_update(
    hass: HomeAssistant,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
    mock_connection: MockConnection,
    freezer_ticker: Any,
) -> None:
    """Test out of band pushed value, update directly and seed the next update."""
    entity_id = "number.heating_offset_climate_system_1_40031"
    coil_id = 40031

    coils[coil_id] = 10
    await async_add_model(hass, Model.S320)

    assert hass.states.get(entity_id) == snapshot(name="1. initial values")

    mock_connection.mock_coil_update(coil_id, 20)
    assert hass.states.get(entity_id) == snapshot(name="2. pushed values")

    coils[coil_id] = 30
    await freezer_ticker(60)

    assert hass.states.get(entity_id) == snapshot(name="3. seeded values")

    await freezer_ticker(60)

    assert hass.states.get(entity_id) == snapshot(name="4. final values")


async def test_shutdown(
    hass: HomeAssistant,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    mock_connection: MockConnection,
    freezer_ticker: Any,
) -> None:
    """Check that shutdown, cancel a long running update."""
    coils[40031] = 10

    entry = await async_add_model(hass, Model.S320)
    mock_connection.start.assert_called_once()

    done = asyncio.Event()
    hang = asyncio.Event()

    async def _read_coil_hang(coil: Coil, timeout: float = 0) -> CoilData:
        try:
            hang.set()
            await done.wait()  # infinite wait
        except asyncio.CancelledError:
            done.set()

    mock_connection.read_coil = _read_coil_hang

    await freezer_ticker(60, block=False)
    await hang.wait()

    await hass.config_entries.async_unload(entry.entry_id)

    assert done.is_set()
    mock_connection.stop.assert_called_once()

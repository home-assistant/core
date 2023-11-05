"""Test the Nibe Heat Pump config flow."""
from typing import Any
from unittest.mock import patch

from nibe.coil import CoilData
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
    """Test setting of value."""
    coils[40031] = 10
    coils[40035] = None

    await async_add_model(hass, Model.S320)

    data = hass.states.get("number.heating_offset_climate_system_1_40031")
    assert data == snapshot(name="Sensor is available")

    data = hass.states.get("number.min_supply_climate_system_1_40035")
    assert data == snapshot(name="Sensor is not available")


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
    heatpump = mock_connection.heatpump

    assert hass.states.get(entity_id) == snapshot(name="1. initial values")

    coils[coil_id] = 30
    coil = heatpump.get_coil_by_address(coil_id)
    heatpump.notify_coil_update(CoilData(coil, 20))

    assert hass.states.get(entity_id) == snapshot(name="2. pushed values")

    await freezer_ticker(60)

    assert hass.states.get(entity_id) == snapshot(name="3. seeded values")

    await freezer_ticker(60)

    assert hass.states.get(entity_id) == snapshot(name="4. final values")

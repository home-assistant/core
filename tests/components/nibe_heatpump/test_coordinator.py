"""Test the Nibe Heat Pump config flow."""

import asyncio
from typing import Any
from unittest.mock import patch

from nibe.coil import Coil, CoilData
from nibe.heatpump import Model
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import MockConnection, async_add_model


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_partial_refresh(
    hass: HomeAssistant,
    coils: dict[int, Any],
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_invalid_coil(
    hass: HomeAssistant,
    coils: dict[int, Any],
    snapshot: SnapshotAssertion,
    freezer_ticker: Any,
) -> None:
    """Test coordinator marks entities unavailable with missing coils."""
    entity_id = "number.heating_offset_climate_system_1_40031"
    coil_id = 40031

    coils[coil_id] = 10
    await async_add_model(hass, Model.S320)

    assert hass.states.get(entity_id) == snapshot(name="Sensor is available")

    coils.pop(coil_id)
    await freezer_ticker(60)

    assert hass.states.get(entity_id) == snapshot(name="Sensor is not available")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_pushed_update(
    hass: HomeAssistant,
    coils: dict[int, Any],
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("seeded_address", "read_address"),
    [
        pytest.param(40031, 40035, id="broadcast-after-seeded-value-captured"),
        pytest.param(40035, 40031, id="broadcast-before-read-response-consumed"),
    ],
)
async def test_pushed_update_during_refresh(
    hass: HomeAssistant,
    coils: dict[int, float],
    mock_connection: MockConnection,
    seeded_address: int,
    read_address: int,
) -> None:
    """Test that a completed polling batch preserves newer pushed values."""
    entity_id = "number.heating_offset_climate_system_1_40031"
    coils[40031] = 10
    coils[40035] = 20

    entry = await async_add_model(hass, Model.S320)
    coordinator = entry.runtime_data
    mock_connection.mock_coil_update(seeded_address, 20)

    async def read_coil(coil: Coil, timeout: float = 0) -> CoilData:
        assert coil.address == read_address
        data = CoilData(coil, 20)
        # NibeGW publishes read replies before the polling iterator consumes them.
        mock_connection.heatpump.notify_coil_update(data)
        mock_connection.mock_coil_update(40031, 21)
        mock_connection.mock_coil_update(40031, 22)
        assert hass.states.get(entity_id).state == "22.0"
        return data

    with patch.object(mock_connection, "read_coil", side_effect=read_coil):
        await coordinator.async_refresh()

    assert hass.states.get(entity_id).state == "22.0"
    assert coordinator.data[40031].value == 22
    assert coordinator.data[40035].value == 20


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_pushed_update_during_partial_refresh(
    hass: HomeAssistant,
    coils: dict[int, float | None],
    mock_connection: MockConnection,
) -> None:
    """Test that a partial polling batch preserves broadcasts for failed coils."""
    entity_id = "number.heating_offset_climate_system_1_40031"
    coils[30002] = 10
    coils[40031] = 10
    coils[40035] = 20

    entry = await async_add_model(hass, Model.S320)
    coordinator = entry.runtime_data
    assert 30002 not in coordinator.context_callbacks
    coils[40031] = None
    read_coil_original = mock_connection.read_coil

    async def read_coil(coil: Coil, timeout: float = 0) -> CoilData:
        data = await read_coil_original(coil, timeout)
        assert coil.address == 40035
        # The earlier read failed, but its broadcast arrives during this read.
        mock_connection.mock_coil_update(40031, 22)
        mock_connection.mock_coil_update(30002, 30)
        mock_connection.heatpump.notify_coil_update(data)
        assert hass.states.get(entity_id).state == "22.0"
        return data

    with patch.object(mock_connection, "read_coil", side_effect=read_coil):
        await coordinator.async_refresh()

    assert hass.states.get(entity_id).state == "22.0"
    assert coordinator.data[40031].value == 22
    assert coordinator.data[40035].value == 20
    assert 30002 not in coordinator.data
    assert coordinator.last_update_success


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_shutdown(
    hass: HomeAssistant,
    coils: dict[int, Any],
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

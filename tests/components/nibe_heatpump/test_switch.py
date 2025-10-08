"""Test the Nibe Heat Pump switch entities."""

from typing import Any
from unittest.mock import AsyncMock, patch

from nibe.coil import CoilData
from nibe.heatpump import Model
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_PLATFORM,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_add_model

from tests.common import snapshot_platform


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize(
    ("model", "address", "value"),
    [
        (Model.F1255, 48043, "INACTIVE"),
        (Model.F1255, 48043, "ACTIVE"),
        (Model.F1255, 48071, "OFF"),
        (Model.F1255, 48071, "ON"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model: Model,
    address: int,
    value: Any,
    coils: dict[int, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting of value."""
    coils[address] = value

    entry = await async_add_model(hass, model)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("model", "address", "entity_id", "state"),
    [
        (Model.F1255, 48043, "switch.holiday_activated_48043", "INACTIVE"),
        (Model.F1255, 48071, "switch.flm_1_accessory_48071", "OFF"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_turn_on(
    hass: HomeAssistant,
    mock_connection: AsyncMock,
    model: Model,
    entity_id: str,
    address: int,
    state: Any,
    coils: dict[int, Any],
) -> None:
    """Test setting of value."""
    coils[address] = state

    await async_add_model(hass, model)

    # Write value
    await hass.services.async_call(
        SWITCH_PLATFORM,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # Verify written
    args = mock_connection.write_coil.call_args
    assert args
    coil = args.args[0]
    assert isinstance(coil, CoilData)
    assert coil.coil.address == address
    assert coil.raw_value == 1


@pytest.mark.parametrize(
    ("model", "address", "entity_id", "state"),
    [
        (Model.F1255, 48043, "switch.holiday_activated_48043", "INACTIVE"),
        (Model.F1255, 48071, "switch.flm_1_accessory_48071", "ON"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_turn_off(
    hass: HomeAssistant,
    mock_connection: AsyncMock,
    model: Model,
    entity_id: str,
    address: int,
    state: Any,
    coils: dict[int, Any],
) -> None:
    """Test setting of value."""
    coils[address] = state

    await async_add_model(hass, model)

    # Write value
    await hass.services.async_call(
        SWITCH_PLATFORM,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # Verify written
    args = mock_connection.write_coil.call_args
    assert args
    coil = args.args[0]
    assert isinstance(coil, CoilData)
    assert coil.coil.address == address
    assert coil.raw_value == 0

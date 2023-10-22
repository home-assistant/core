"""Test the Nibe Heat Pump config flow."""
from typing import Any
from unittest.mock import AsyncMock, patch

from nibe.coil import CoilData
from nibe.heatpump import Model
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import async_add_model


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.mark.parametrize(
    ("model", "address", "entity_id", "value"),
    [
        # Tests for S series coils with min/max
        (Model.S320, 40031, "number.heating_offset_climate_system_1_40031", 10),
        (Model.S320, 40031, "number.heating_offset_climate_system_1_40031", -10),
        (Model.S320, 40031, "number.heating_offset_climate_system_1_40031", None),
        # Tests for F series coils with min/max
        (Model.F1155, 47011, "number.heat_offset_s1_47011", 10),
        (Model.F1155, 47011, "number.heat_offset_s1_47011", -10),
        (Model.F1155, 47062, "number.heat_offset_s1_47011", None),
        # Tests for F series coils without min/max
        (Model.F750, 47062, "number.hw_charge_offset_47062", 10),
        (Model.F750, 47062, "number.hw_charge_offset_47062", -10),
        (Model.F750, 47062, "number.hw_charge_offset_47062", None),
    ],
)
async def test_update(
    hass: HomeAssistant,
    model: Model,
    entity_id: str,
    address: int,
    value: Any,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting of value."""
    coils[address] = value

    await async_add_model(hass, model)

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state == snapshot


@pytest.mark.parametrize(
    ("model", "address", "entity_id", "value"),
    [
        (Model.S320, 40031, "number.heating_offset_climate_system_1_40031", 10),
        (Model.S320, 40031, "number.heating_offset_climate_system_1_40031", -10),
        (Model.F1155, 47011, "number.heat_offset_s1_47011", 10),
        (Model.F1155, 47011, "number.heat_offset_s1_47011", -10),
        (Model.F750, 47062, "number.hw_charge_offset_47062", 10),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_connection: AsyncMock,
    model: Model,
    entity_id: str,
    address: int,
    value: Any,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
) -> None:
    """Test setting of value."""
    coils[address] = 0

    await async_add_model(hass, model)

    await hass.async_block_till_done()
    assert hass.states.get(entity_id)

    # Write value
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    await hass.async_block_till_done()

    # Verify written
    args = mock_connection.write_coil.call_args
    assert args
    coil = args.args[0]
    assert isinstance(coil, CoilData)
    assert coil.coil.address == address
    assert coil.value == value

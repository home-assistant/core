"""Test the Nibe Heat Pump number entities."""

from typing import Any
from unittest.mock import AsyncMock, patch

from nibe.coil import CoilData
from nibe.exceptions import WriteDeniedException, WriteException, WriteTimeoutException
from nibe.heatpump import Model
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update(
    hass: HomeAssistant,
    model: Model,
    entity_id: str,
    address: int,
    value: Any,
    coils: dict[int, Any],
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
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_value(
    hass: HomeAssistant,
    mock_connection: AsyncMock,
    model: Model,
    entity_id: str,
    address: int,
    value: Any,
    coils: dict[int, Any],
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


@pytest.mark.parametrize(
    ("exception", "translation_key", "translation_placeholders"),
    [
        (
            WriteTimeoutException("timeout writing"),
            "write_timeout",
            {"address": "47398"},
        ),
        (
            WriteException("failed"),
            "write_failed",
            {
                "address": "47398",
                "value": "25.0",
                "error": "failed",
            },
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_value_fail(
    hass: HomeAssistant,
    mock_connection: AsyncMock,
    exception: Exception,
    translation_key: str,
    translation_placeholders: dict[str, Any],
    coils: dict[int, Any],
) -> None:
    """Test setting of value."""

    value = 25
    model = Model.F1155
    address = 47398
    entity_id = "number.room_sensor_setpoint_s1_47398"
    coils[address] = 0

    await async_add_model(hass, model)

    await hass.async_block_till_done()
    assert hass.states.get(entity_id)

    mock_connection.write_coil.side_effect = exception

    # Write value
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )
    assert exc_info.value.translation_domain == "nibe_heatpump"
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == translation_placeholders


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_value_same(
    hass: HomeAssistant,
    mock_connection: AsyncMock,
    coils: dict[int, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting a value, which the pump will reject."""

    value = 25
    model = Model.F1155
    address = 47398
    entity_id = "number.room_sensor_setpoint_s1_47398"
    coils[address] = 0

    await async_add_model(hass, model)

    await hass.async_block_till_done()
    assert hass.states.get(entity_id)

    mock_connection.write_coil.side_effect = WriteDeniedException()

    # Write value
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    # Verify attempt was done
    args = mock_connection.write_coil.call_args
    assert args
    coil = args.args[0]
    assert isinstance(coil, CoilData)
    assert coil.coil.address == address
    assert coil.value == value

    # State should have been set
    assert hass.states.get(entity_id) == snapshot

"""Tests for the BACnet select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.bacnet.bacnet_client import (
    BACnetObjectInfo,
    BACnetWriteError,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_DEVICE_KEY, init_integration


async def test_select_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that multi-state output objects create select entities."""
    await init_integration(hass)

    # Fan Speed (multi-state-output,0) - value 1 maps to "Low"
    state = hass.states.get("select.test_hvac_controller_fan_speed")
    assert state is not None
    assert state.state == "Low"
    assert state.attributes.get("options") == ["Low", "Medium", "High"]


async def test_select_count(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test the correct number of select entities are created."""
    await init_integration(hass)

    select_states = hass.states.async_entity_ids("select")
    # We expect 1 select: multi-state-output,0 (Fan Speed)
    assert len(select_states) == 1


async def test_select_option(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test selecting an option on a select entity."""
    await init_integration(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.test_hvac_controller_fan_speed",
            ATTR_OPTION: "High",
        },
        blocking=True,
    )

    # "High" is index 2 in state_text, so 1-indexed value is 3
    mock_bacnet_client.write_present_value.assert_called_once_with(
        "192.168.1.100:47808",
        "multi-state-output",
        0,
        3,
    )


async def test_select_option_write_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test error handling when write fails."""
    await init_integration(hass)

    mock_bacnet_client.write_present_value.side_effect = BACnetWriteError(
        "write failed"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.test_hvac_controller_fan_speed",
                ATTR_OPTION: "Medium",
            },
            blocking=True,
        )


async def test_select_skipped_without_state_text(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that multi-state output without state_text does not create a select entity."""
    # Replace the object list with one that has no state_text
    mock_bacnet_client.get_device_objects.return_value = [
        BACnetObjectInfo(
            object_type="multi-state-output",
            object_instance=0,
            object_name="Fan Speed",
            present_value=1,
            units="",
        ),
    ]

    await init_integration(hass)

    select_states = hass.states.async_entity_ids("select")
    assert len(select_states) == 0


async def test_select_invalid_option(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test error when selecting an invalid option."""
    await init_integration(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.test_hvac_controller_fan_speed",
                ATTR_OPTION: "Turbo",
            },
            blocking=True,
        )


async def test_select_none_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test select entity handles None value."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator.data.values["multi-state-output,0"] = None
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("select.test_hvac_controller_fan_speed")
    assert state is not None
    assert state.state == "unknown"


async def test_select_int_value_out_of_range(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test select entity handles int value out of state_text range."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Value 99 is out of range for ["Low", "Medium", "High"]
    coordinator.data.values["multi-state-output,0"] = 99
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("select.test_hvac_controller_fan_speed")
    assert state is not None
    # Out-of-range value returns str(99) from current_option, but since "99"
    # is not in the options list, HA reports the state as "unknown"
    assert state.state == "unknown"


async def test_select_updated_state_text(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test select entity updates options when state_text changes."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Simulate re-discovery updating state_text
    for obj in coordinator.data.objects:
        if obj.object_type == "multi-state-output" and obj.object_instance == 0:
            obj.state_text = ["Off", "Low", "Medium", "High", "Turbo"]
            break

    coordinator.data.values["multi-state-output,0"] = 5
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("select.test_hvac_controller_fan_speed")
    assert state is not None
    assert state.state == "Turbo"

    # Trigger a second update so the updated options list is written to state
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("select.test_hvac_controller_fan_speed")
    assert state.attributes.get("options") == ["Off", "Low", "Medium", "High", "Turbo"]


async def test_select_timeout_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test error handling when write times out."""
    await init_integration(hass)

    mock_bacnet_client.write_present_value.side_effect = TimeoutError("timeout")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.test_hvac_controller_fan_speed",
                ATTR_OPTION: "Medium",
            },
            blocking=True,
        )

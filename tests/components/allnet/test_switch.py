"""Tests for the ALLNET switch platform."""

from unittest.mock import AsyncMock

from allnet.exceptions import AllnetCommandError
import pytest

from homeassistant.components.allnet.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_UNIQUE_ID


@pytest.mark.asyncio
async def test_switch_entities_created(hass: HomeAssistant, setup_integration) -> None:
    """Test that switch entities are created for SWITCH channels."""
    state_r0 = hass.states.get("switch.allnet_test_device_relay_1")
    state_r1 = hass.states.get("switch.allnet_test_device_relay_2")

    assert state_r0 is not None
    assert state_r1 is not None


@pytest.mark.asyncio
async def test_switch_is_off(hass: HomeAssistant, setup_integration) -> None:
    """Test that switch with value=False reports STATE_OFF."""
    state = hass.states.get("switch.allnet_test_device_relay_1")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.asyncio
async def test_switch_is_on(hass: HomeAssistant, setup_integration) -> None:
    """Test that switch with value=True reports STATE_ON."""
    state = hass.states.get("switch.allnet_test_device_relay_2")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.asyncio
async def test_turn_on_calls_set_channel_state(hass: HomeAssistant, setup_integration) -> None:
    """Test that turn_on calls async_set_channel_state with state=True."""
    entry = setup_integration
    client = entry.runtime_data.client

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.allnet_test_device_relay_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client.async_set_channel_state.assert_awaited_once_with("relay_0", True)


@pytest.mark.asyncio
async def test_turn_off_calls_set_channel_state(hass: HomeAssistant, setup_integration) -> None:
    """Test that turn_off calls async_set_channel_state with state=False."""
    entry = setup_integration
    client = entry.runtime_data.client

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.allnet_test_device_relay_2"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client.async_set_channel_state.assert_awaited_once_with("relay_1", False)


@pytest.mark.asyncio
async def test_turn_on_raises_ha_error_on_command_error(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test that AllnetCommandError is converted to HomeAssistantError."""
    entry = setup_integration
    client = entry.runtime_data.client
    client.async_set_channel_state = AsyncMock(
        side_effect=AllnetCommandError("relay failed")
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.allnet_test_device_relay_1"},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_switch_unique_id(hass: HomeAssistant, setup_integration) -> None:
    """Test that switch entities have the correct unique_id."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get_entity_id(
        "switch", DOMAIN, f"{TEST_UNIQUE_ID}_relay_0_switch"
    )
    assert entry is not None

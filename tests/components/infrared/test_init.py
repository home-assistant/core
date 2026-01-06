"""Tests for the Infrared integration setup."""

import pytest

from homeassistant.components.infrared import (
    DATA_COMPONENT,
    DOMAIN,
    InfraredEntityFeature,
    InfraredProtocolType,
    NECInfraredCommand,
    async_get_entities,
    async_send_command,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .conftest import MockInfraredEntity


async def test_setup(hass: HomeAssistant) -> None:
    """Test Infrared integration setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Verify the component is loaded
    assert DATA_COMPONENT in hass.data


async def test_get_entities_empty(hass: HomeAssistant) -> None:
    """Test getting entities when none are registered."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entities = async_get_entities(hass)
    assert entities == []


async def test_get_entities_filter_by_protocol(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test filtering entities by protocol support."""
    # Add the mock entity to the component
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    # Get all entities
    all_entities = async_get_entities(hass)
    assert len(all_entities) == 1
    assert all_entities[0] is mock_infrared_entity

    # Filter by NEC protocol (should match)
    nec_entities = async_get_entities(hass, protocols=[InfraredProtocolType.NEC])
    assert len(nec_entities) == 1

    # Filter by Samsung protocol (should not match since mock only supports NEC and PULSE_WIDTH)
    samsung_entities = async_get_entities(
        hass, protocols=[InfraredProtocolType.SAMSUNG]
    )
    assert len(samsung_entities) == 0


async def test_infrared_entity_send_command(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test sending command via infrared entity."""
    # Add the mock entity to the component
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    # Create a test command
    command = NECInfraredCommand(
        repeat_count=1,
        address=0x04FB,
        command=0x08F7,
    )

    # Send command
    await mock_infrared_entity.async_send_command(command)

    # Verify command was recorded
    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] is command


async def test_infrared_entity_features(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test infrared entity features property."""
    assert mock_infrared_entity.supported_features == InfraredEntityFeature.TRANSMIT
    assert InfraredProtocolType.NEC in mock_infrared_entity.supported_protocols
    assert InfraredProtocolType.PULSE_WIDTH in mock_infrared_entity.supported_protocols


async def test_async_send_command_success(
    hass: HomeAssistant,
    init_integration: None,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Test sending command via async_send_command helper."""
    # Add the mock entity to the component
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([mock_infrared_entity])

    command = NECInfraredCommand(repeat_count=1, address=0x04FB, command=0x08F7)

    await async_send_command(hass, "infrared.test_ir_transmitter", command)

    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] is command


async def test_async_send_command_entity_not_found(
    hass: HomeAssistant, init_integration: None
) -> None:
    """Test async_send_command raises error when entity not found."""
    command = NECInfraredCommand(repeat_count=1, address=0x04FB, command=0x08F7)

    with pytest.raises(HomeAssistantError, match="entity_not_found"):
        await async_send_command(hass, "infrared.nonexistent_entity", command)


async def test_async_send_command_component_not_loaded(hass: HomeAssistant) -> None:
    """Test async_send_command raises error when component not loaded."""
    command = NECInfraredCommand(repeat_count=1, address=0x04FB, command=0x08F7)

    with pytest.raises(HomeAssistantError, match="Infrared component not loaded"):
        await async_send_command(hass, "infrared.some_entity", command)

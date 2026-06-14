"""Common test tools for the Infrared integration."""

from infrared_protocols.commands import Command as InfraredCommand

from homeassistant.components.infrared import (
    DATA_COMPONENT,
    InfraredEmitterEntity,
    InfraredEntity,
    InfraredReceiverEntity,
)
from homeassistant.components.infrared.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


class MockInfraredEntity(InfraredEntity):
    """Mock deprecated infrared entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test IR emitter"

    def __init__(self, unique_id: str) -> None:
        """Initialize mock entity."""
        self._attr_unique_id = unique_id
        self.send_command_calls: list[InfraredCommand] = []

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Mock send command."""
        self.send_command_calls.append(command)


class MockInfraredEmitterEntity(InfraredEmitterEntity):
    """Mock infrared emitter entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test IR emitter"

    def __init__(self, unique_id: str) -> None:
        """Initialize mock entity."""
        self._attr_unique_id = unique_id
        self.send_command_calls: list[InfraredCommand] = []

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Mock send command."""
        self.send_command_calls.append(command)


class MockInfraredReceiverEntity(InfraredReceiverEntity):
    """Mock infrared receiver entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test IR receiver"

    def __init__(self, unique_id: str) -> None:
        """Initialize mock receiver entity."""
        self._attr_unique_id = unique_id


async def init_infrared_fixture_helper(hass: HomeAssistant) -> None:
    """Set up the Infrared integration for testing."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def mock_infrared_emitter_entity_fixture_helper(
    hass: HomeAssistant,
) -> MockInfraredEmitterEntity:
    """Add a mock infrared emitter entity to the running integration."""
    entity = MockInfraredEmitterEntity("test_ir_emitter")
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([entity])
    return entity


async def mock_infrared_receiver_entity_fixture_helper(
    hass: HomeAssistant,
) -> MockInfraredReceiverEntity:
    """Add a mock infrared receiver entity to the running integration."""
    entity = MockInfraredReceiverEntity("test_ir_receiver")
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([entity])
    return entity

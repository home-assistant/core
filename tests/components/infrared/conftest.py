"""Common fixtures for the Infrared tests."""

from infrared_protocols.commands import Command as InfraredCommand
import pytest

from homeassistant.components.infrared import (
    InfraredEmitterEntity,
    InfraredReceiverEntity,
)
from homeassistant.components.infrared.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def init_integration(hass: HomeAssistant) -> None:
    """Set up the Infrared integration for testing."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


class MockInfraredEmitterEntity(InfraredEmitterEntity):
    """Mock infrared emitter entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test IR emitter"

    def __init__(self, unique_id: str) -> None:
        """Initialize mock entity."""
        super().__init__()
        self._attr_unique_id = unique_id
        self.send_command_calls: list[InfraredCommand] = []

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Mock send command."""
        self.send_command_calls.append(command)


@pytest.fixture
def mock_infrared_emitter_entity() -> MockInfraredEmitterEntity:
    """Return a mock infrared emitter entity."""
    return MockInfraredEmitterEntity("test_ir_emitter")


class MockInfraredReceiverEntity(InfraredReceiverEntity):
    """Mock infrared receiver entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test IR receiver"

    def __init__(self, unique_id: str) -> None:
        """Initialize mock receiver entity."""
        self._attr_unique_id = unique_id


@pytest.fixture
def mock_infrared_receiver_entity() -> MockInfraredReceiverEntity:
    """Return a mock infrared receiver entity."""
    return MockInfraredReceiverEntity("test_ir_receiver")

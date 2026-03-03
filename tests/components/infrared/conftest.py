"""Common fixtures for the Infrared tests."""

from infrared_protocols import Command as InfraredCommand
import pytest

from homeassistant.components.infrared import InfraredEntity
from homeassistant.components.infrared.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def init_integration(hass: HomeAssistant) -> None:
    """Set up the Infrared integration for testing."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


class MockInfraredEntity(InfraredEntity):
    """Mock infrared entity for testing."""

    _attr_has_entity_name = True
    _attr_name = "Test IR transmitter"

    def __init__(self, unique_id: str) -> None:
        """Initialize mock entity."""
        self._attr_unique_id = unique_id
        self.send_command_calls: list[InfraredCommand] = []

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Mock send command."""
        self.send_command_calls.append(command)


@pytest.fixture
def mock_infrared_entity() -> MockInfraredEntity:
    """Return a mock infrared entity."""
    return MockInfraredEntity("test_ir_transmitter")

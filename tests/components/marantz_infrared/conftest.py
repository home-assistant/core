"""Common fixtures for the Marantz Infrared tests."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.marantz.audio import MarantzAudioCode
from infrared_protocols.commands import Command as InfraredCommand
import pytest

from homeassistant.components.infrared import (
    DATA_COMPONENT as INFRARED_DATA_COMPONENT,
    DOMAIN as INFRARED_DOMAIN,
    InfraredEntity,
)
from homeassistant.components.marantz_infrared import PLATFORMS
from homeassistant.components.marantz_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_MODEL,
    DOMAIN,
    MODELS,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.common import MockConfigEntry

MOCK_INFRARED_ENTITY_ID = "infrared.test_ir_transmitter"
MOCK_MODEL = "pm6006_integrated_amplifier"


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
def model(request: pytest.FixtureRequest) -> str:
    """Return the Marantz model slug to use for the config entry.

    Override with ``@pytest.mark.parametrize("model", [...], indirect=True)``.
    """
    return getattr(request, "param", MOCK_MODEL)


@pytest.fixture
def mock_config_entry(model: str) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title=MODELS[model].name,
        data={
            CONF_MODEL: model,
            CONF_INFRARED_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
        unique_id=f"{model}_{MOCK_INFRARED_ENTITY_ID}",
    )


def media_player_entity_id(model: str) -> str:
    """Return the expected media_player entity_id for a model slug."""
    return f"media_player.marantz_{slugify(MODELS[model].name)}"


@pytest.fixture
def mock_infrared_entity() -> MockInfraredEntity:
    """Return a mock infrared entity."""
    return MockInfraredEntity("test_ir_transmitter")


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_marantz_to_command() -> Generator[None]:
    """Make ``MarantzAudioCode.to_command`` return the code itself.

    This lets tests assert on the high-level code enum value rather
    than on the raw RC-5 timings.
    """

    def _identity(self: MarantzAudioCode, repeat_count: int = 0, *, toggle: int = 0):
        return self

    with patch.object(MarantzAudioCode, "to_command", _identity):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_entity: MockInfraredEntity,
    mock_marantz_to_command: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Marantz Infrared integration for testing."""
    assert await async_setup_component(hass, INFRARED_DOMAIN, {})
    await hass.async_block_till_done()

    infrared_component = hass.data[INFRARED_DATA_COMPONENT]
    await infrared_component.async_add_entities([mock_infrared_entity])

    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.marantz_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry

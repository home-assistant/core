"""Common fixtures for the Marantz Infrared tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from infrared_protocols.codes.marantz.audio import MarantzAudioCode
import pytest

from homeassistant.components.marantz_infrared import PLATFORMS
from homeassistant.components.marantz_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    MODELS,
)
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
)
from tests.components.infrared.common import MockInfraredEmitterEntity

MOCK_MODEL = "pm6006_integrated_amplifier"


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
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        },
        unique_id=f"{model}_{MOCK_INFRARED_EMITTER_ENTITY_ID}",
    )


def media_player_entity_id(model: str) -> str:
    """Return the expected media_player entity_id for a model slug."""
    return f"media_player.marantz_{slugify(MODELS[model].name)}"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_marantz_to_command() -> Generator[MagicMock]:
    """Patch ``MarantzAudioCode.to_command`` to return the code itself.

    This lets tests assert on the high-level code enum value rather than
    on the raw RC-5 timings. The mock is yielded so tests can also
    inspect call arguments, such as the RC-5 toggle bit.
    """
    with patch.object(
        MarantzAudioCode,
        "to_command",
        autospec=True,
        side_effect=lambda self, **kwargs: self,
    ) as mock:
        yield mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_marantz_to_command: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Marantz Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.marantz_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry

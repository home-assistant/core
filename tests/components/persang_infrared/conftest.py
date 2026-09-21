"""Common fixtures for the Persang Infrared tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from infrared_protocols.codes.persang.speaker import PersangSpeakerCode
import pytest

from homeassistant.components.persang_infrared import PLATFORMS
from homeassistant.components.persang_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
)
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="Persang speaker",
        data={CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID},
        unique_id=MOCK_INFRARED_EMITTER_ENTITY_ID,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
def mock_persang_to_command() -> Generator[MagicMock]:
    """Patch ``PersangSpeakerCode.to_command`` to return the code itself.

    This lets tests assert on the code enum rather than on raw NEC timings.
    """
    with patch.object(
        PersangSpeakerCode,
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
    mock_persang_to_command: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Persang Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.persang_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry

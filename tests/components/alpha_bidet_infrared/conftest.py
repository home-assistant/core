"""Common fixtures for the Alpha Bidet Infrared tests."""

from unittest.mock import patch

from infrared_protocols.codes.alpha_bidet.models import AlphaBidetModel
import pytest

from homeassistant.components.alpha_bidet_infrared import PLATFORMS
from homeassistant.components.alpha_bidet_infrared.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.const import CONF_MODEL, Platform
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
        title="Alpha Bidet JX2",
        data={
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_MODEL: AlphaBidetModel.JX2.value,
        },
        unique_id=MOCK_INFRARED_EMITTER_ENTITY_ID,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Alpha Bidet Infrared integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.alpha_bidet_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry

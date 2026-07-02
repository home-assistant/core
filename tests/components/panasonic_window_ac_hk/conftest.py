"""Common fixtures for the Panasonic Window A/C tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.panasonic_window_ac_hk import PLATFORMS
from homeassistant.components.panasonic_window_ac_hk.const import (
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID as MOCK_INFRARED_ENTITY_ID


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTEST0000000000000000000",
        title="Panasonic Window AC (Hong Kong)",
        data={
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
        },
        unique_id=MOCK_INFRARED_ENTITY_ID,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Panasonic window A/C integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.panasonic_window_ac_hk.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry

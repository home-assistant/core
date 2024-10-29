"""Common fixtures for the Color extractor tests."""

import pytest

from homeassistant.components.color_extractor.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
async def config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(domain=DOMAIN, data={})


@pytest.fixture
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Add config entry for color extractor."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

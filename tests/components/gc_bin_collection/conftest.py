"""Fixtures for Gold Coast Bin Collection tests."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.gc_bin_collection.const import CONF_PROPERTY_ID, DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_ADDRESS = "1 Example St, Surfers Paradise QLD 4217"
MOCK_PROPERTY_ID = "123456"

MOCK_BIN_DATA = {
    "landfill": datetime.date(2026, 6, 9),
    "recycling": datetime.date(2026, 6, 16),
    "organics": datetime.date(2026, 6, 9),
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_ADDRESS,
        data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_PROPERTY_ID: MOCK_PROPERTY_ID,
        },
        unique_id=MOCK_PROPERTY_ID,
    )


@pytest.fixture
def mock_gcbinspy():
    """Return a mock GoldCoastBins client."""
    with patch(
        "homeassistant.components.gc_bin_collection.coordinator.GoldCoastBins"
    ) as mock_class:
        client = MagicMock()
        client.property_id.return_value = MOCK_PROPERTY_ID
        client.next_landfill.return_value = MOCK_BIN_DATA["landfill"]
        client.next_recycling.return_value = MOCK_BIN_DATA["recycling"]
        client.next_organics.return_value = MOCK_BIN_DATA["organics"]
        mock_class.return_value = client
        yield client


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gcbinspy: MagicMock,
) -> None:
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

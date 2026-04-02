"""Fixtures for the BIR integration tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, patch

from pybirno import Address, WastePickup as BirWastePickup
import pytest

from homeassistant.components.bir.const import CONF_PROPERTY_ID, DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_PROPERTY_ID = "12345"
MOCK_ADDRESS = "Testveien 1, Bergen"

MOCK_BIR_PICKUPS = [
    BirWastePickup(
        date=date(2026, 4, 15),
        waste_type="mixed_waste",
        waste_type_name="Restavfall",
        waste_type_id="1",
        frequency_type=0,
        frequency_interval=0,
    ),
    BirWastePickup(
        date=date(2026, 4, 20),
        waste_type="paper_and_plastic",
        waste_type_name="Papir",
        waste_type_id="2",
        frequency_type=0,
        frequency_interval=0,
    ),
    BirWastePickup(
        date=date(2026, 4, 10),
        waste_type="food_waste",
        waste_type_name="Matavfall",
        waste_type_id="3",
        frequency_type=0,
        frequency_interval=0,
    ),
    BirWastePickup(
        date=date(2026, 5, 1),
        waste_type="glass_and_metal_packaging",
        waste_type_name="Glass og metallemballasje",
        waste_type_id="4",
        frequency_type=0,
        frequency_interval=0,
    ),
]

MOCK_ADDRESS_RESULTS = [
    Address(
        property_id=MOCK_PROPERTY_ID,
        address=MOCK_ADDRESS,
        municipality="Bergen",
        municipality_number="4601",
    ),
    Address(
        property_id="67890",
        address="Testveien 2, Bergen",
        municipality="Bergen",
        municipality_number="4601",
    ),
]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=MOCK_ADDRESS,
        domain=DOMAIN,
        data={
            CONF_PROPERTY_ID: MOCK_PROPERTY_ID,
            CONF_ADDRESS: MOCK_ADDRESS,
        },
        unique_id=f"bir_{MOCK_PROPERTY_ID}",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.bir.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_bir_client() -> Generator[AsyncMock]:
    """Return a mocked BirClient."""
    with patch(
        "homeassistant.components.bir.coordinator.BirClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.authenticate = AsyncMock()
        client.get_pickups = AsyncMock(return_value=MOCK_BIR_PICKUPS)
        yield client


@pytest.fixture
def mock_address_search() -> Generator[AsyncMock]:
    """Return a mocked address search."""
    with patch(
        "homeassistant.components.bir.config_flow.BirClient.search_addresses",
        new_callable=AsyncMock,
        return_value=MOCK_ADDRESS_RESULTS,
    ) as mock_search:
        yield mock_search


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bir_client: AsyncMock,
) -> MockConfigEntry:
    """Set up the BIR integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

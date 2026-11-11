"""Fixtures for the Junker integration tests."""

from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.junker.const import (
    CONF_MUNICIPALITY,
    CONF_WASTE_TYPES,
    DOMAIN,
)
from homeassistant.components.junker.junker_api import Collection
from homeassistant.core import HomeAssistant

TEST_MUNICIPALITY = "Test municipality"


@pytest.fixture(name="collections")
def collections_fixture() -> list[Collection]:
    """Return a Junker collection schedule."""
    return [
        Collection(date(2026, 11, 11), "Organic waste"),
        Collection(date(2026, 11, 11), "Paper"),
        Collection(date(2026, 11, 12), "General waste"),
    ]


@pytest.fixture(name="client")
def client_fixture(collections: list[Collection]) -> Mock:
    """Return a mocked Junker client."""
    return Mock(async_get_collections=AsyncMock(return_value=collections))


@pytest.fixture(name="mock_junker_client")
def mock_junker_client_fixture(client: Mock) -> Generator[None]:
    """Patch the Junker client used by the integration."""
    with (
        patch("homeassistant.components.junker.JunkerClient", return_value=client),
        patch(
            "homeassistant.components.junker.config_flow.JunkerClient",
            return_value=client,
        ),
    ):
        yield


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Return a Junker config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_MUNICIPALITY,
        data={CONF_MUNICIPALITY: TEST_MUNICIPALITY},
        options={CONF_WASTE_TYPES: {"Organic waste": "Kitchen", "Paper": "Cardboard"}},
        unique_id="test-municipality:all",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="init_integration")
async def init_integration_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_junker_client: None
) -> MockConfigEntry:
    """Set up the Junker integration."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry

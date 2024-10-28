"""Common fixtures for the Suez Water tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.suez_water.const import DOMAIN
from homeassistant.components.suez_water.coordinator import SuezWaterCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_DATA = {
    "username": "test-username",
    "password": "test-password",
    "counter_id": "test-counter",
}


async def create_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create an entry in hass."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Suez mock device",
        data=MOCK_DATA,
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.suez_water.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_coordinator(hass: HomeAssistant) -> SuezWaterCoordinator:
    """Create mock coordinator."""

    return SuezWaterCoordinator(
        hass,
        None,
        MOCK_DATA["counter_id"],
    )

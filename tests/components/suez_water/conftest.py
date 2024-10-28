"""Common fixtures for the Suez Water tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pysuez.client import SuezClient
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
def mock_client() -> Generator[None]:
    """Fixture to mock _get_devices which makes a call to the API."""

    client = SuezClient(
        MOCK_DATA["username"],
        MOCK_DATA["password"],
        MOCK_DATA["counter_id"],
        provider=None,
    )

    with patch(
        "homeassistant.components.suez_water._get_client",
        return_value=client,
    ):
        yield


@pytest.fixture
def mock_coordinator(mock_client: SuezClient, hass: HomeAssistant) -> Generator[None]:
    """Fixture to mock _get_devices which makes a call to the API."""

    coordinator = SuezWaterCoordinator(
        hass,
        mock_client,
        MOCK_DATA["counter_id"],
    )

    with patch(
        "homeassistant.components.suez_water._get_coordinator",
        return_value=coordinator,
    ):
        yield

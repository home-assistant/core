"""Fixtures for easyEnergy integration tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from easyenergy import Electricity, Gas
import pytest

from homeassistant.components.easyenergy.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_json_array_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.easyenergy.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="energy",
        domain=DOMAIN,
        data={},
        unique_id="unique_thingy",
    )


@pytest.fixture
async def mock_easyenergy(hass: HomeAssistant) -> AsyncGenerator[MagicMock]:
    """Return a mocked easyEnergy client."""
    with patch(
        "homeassistant.components.easyenergy.coordinator.EasyEnergy", autospec=True
    ) as easyenergy_mock:
        client = easyenergy_mock.return_value
        client.energy_prices.return_value = Electricity.from_dict(
            await async_load_json_array_fixture(hass, "today_energy.json", DOMAIN)
        )
        client.gas_prices.return_value = Gas.from_dict(
            await async_load_json_array_fixture(hass, "today_gas.json", DOMAIN)
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_easyenergy: MagicMock
) -> MockConfigEntry:
    """Set up the easyEnergy integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry

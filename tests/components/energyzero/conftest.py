"""Fixtures for EnergyZero integration tests."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from energyzero import Electricity, Gas
import pytest

from homeassistant.components.energyzero.const import CONF_GAS, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="energy",
        domain=DOMAIN,
        data={CONF_GAS: True},
        unique_id="unique_thingy",
    )


@pytest.fixture
def mock_energyzero():
    """Return a mocked EnergyZero client."""
    with patch(
        "homeassistant.components.energyzero.coordinator.EnergyZero"
    ) as energyzero_mock:
        client = energyzero_mock.return_value
        client.energy_prices = AsyncMock(
            return_value=Electricity.from_dict(
                json.loads(load_fixture("energyzero/today_energy.json"))
            )
        )
        client.gas_prices = AsyncMock(
            return_value=Gas.from_dict(
                json.loads(load_fixture("energyzero/today_gas.json"))
            )
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_energyzero: MagicMock
) -> MockConfigEntry:
    """Set up the EnergyZero integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry

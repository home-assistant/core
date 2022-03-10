"""Fixtures for HomeWizard integration tests."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from homewizard_energy.models import Data, Device, State
import pytest

from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Product Name (aabbccddeeff)",
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4"},
        unique_id="aabbccddeeff",
    )


@pytest.fixture
def mock_homewizard_energy():
    """Return a mocked P1 Monitor client."""
    api = AsyncMock()
    api.device = AsyncMock(
        return_value=Device.from_dict(
            json.loads(load_fixture("homewizard/device.json"))
        )
    )
    api.data = AsyncMock(
        return_value=Data.from_dict(json.loads(load_fixture("homewizard/data.json")))
    )
    api.state = AsyncMock(
        return_value=State.from_dict(json.loads(load_fixture("homewizard/state.json")))
    )
    return api


@pytest.fixture
def mock_homewizard_energy_minimal():
    """Return a mocked P1 Monitor client."""
    api = AsyncMock()
    api.device = AsyncMock(
        return_value=Device.from_dict(
            json.loads(load_fixture("homewizard/device.json"))
        )
    )
    api.data = AsyncMock(
        return_value=Data.from_dict(
            json.loads(load_fixture("homewizard/data_minimal.json"))
        )
    )
    api.state = AsyncMock(return_value=None)
    return api


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizard_energy: MagicMock,
) -> MockConfigEntry:
    """Set up the HomeWizard integration for testing."""

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        return mock_config_entry

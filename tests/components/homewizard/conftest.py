"""Fixtures for HomeWizard integration tests."""
import json
from unittest.mock import AsyncMock, patch

from homewizard_energy.models import Data, Device, State
import pytest

from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry_data():
    """Return the default mocked config entry data."""
    return {
        "product_name": "Product Name",
        "product_type": "product_type",
        "serial": "aabbccddeeff",
        "name": "Product Name",
        CONF_IP_ADDRESS: "1.2.3.4",
    }


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
def mock_homewizardenergy():
    """Return a mocked P1 meter."""
    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
    ) as device:
        client = device.return_value
        client.device = AsyncMock(
            return_value=Device.from_dict(
                json.loads(load_fixture("homewizard/device.json"))
            )
        )
        client.data = AsyncMock(
            return_value=Data.from_dict(
                json.loads(load_fixture("homewizard/data.json"))
            )
        )
        client.state = AsyncMock(
            return_value=State.from_dict(
                json.loads(load_fixture("homewizard/state.json"))
            )
        )
        yield device


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: AsyncMock,
) -> MockConfigEntry:
    """Set up the HomeWizard integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry

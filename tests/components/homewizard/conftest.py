"""Fixtures for HomeWizard integration tests."""
from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

from homewizard_energy.features import Features
from homewizard_energy.models import Data, Device, State, System
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
    """Return a mocked all-feature device."""
    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
    ) as device:
        client = device.return_value
        client.features = AsyncMock(return_value=Features("HWE-SKT", "3.01"))
        client.device = AsyncMock(
            side_effect=lambda: Device.from_dict(
                json.loads(load_fixture("homewizard/device.json"))
            )
        )
        client.data = AsyncMock(
            side_effect=lambda: Data.from_dict(
                json.loads(load_fixture("homewizard/data.json"))
            )
        )
        client.state = AsyncMock(
            side_effect=lambda: State.from_dict(
                json.loads(load_fixture("homewizard/state.json"))
            )
        )
        client.system = AsyncMock(
            side_effect=lambda: System.from_dict(
                json.loads(load_fixture("homewizard/system.json"))
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


@pytest.fixture
def mock_onboarding() -> Generator[MagicMock, None, None]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        yield mock_onboarding

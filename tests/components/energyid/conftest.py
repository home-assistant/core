"""Common fixtures for the EnergyID tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.energyid.const import DOMAIN
from homeassistant.core import HomeAssistant

from .common import MOCK_CONFIG_ENTRY_DATA, MockConfigEntry, MockMeterCatalog


@pytest.fixture
def mock_webhook_client() -> Generator[AsyncMock]:
    """Provide a mocked webhook client."""
    with patch("homeassistant.components.energyid.WebhookClientAsync") as mock_client:
        client = AsyncMock()
        client.get_policy.return_value = True
        client.get_meter_catalog.return_value = MockMeterCatalog()
        client.post_payload.return_value = None
        mock_client.return_value = client
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock EnergyID config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA,
        title=f"Send {MOCK_CONFIG_ENTRY_DATA['entity_id']} to EnergyID",
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the EnergyID integration in Home Assistant."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

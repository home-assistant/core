from unittest.mock import AsyncMock, patch
from collections.abc import Generator

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from homeassistant.components.solarman.const import DOMAIN

from tests.common import MockConfigEntry, load_json_object_fixture


TEST_HOST = "192.168.1.100"
TEST_PORT = 8080
TEST_DEVICE_SN = "SN1234567890"
TEST_MODEL = "SP-2W-EU"

@pytest.fixture
def device_fixture(request) -> str:
    """Return the device fixtures for a specific device."""
    return request.param

@pytest.fixture
def mock_config_entry(device_fixture: str) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{device_fixture} ({TEST_HOST})",
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            "sn": TEST_DEVICE_SN,
            "model": device_fixture,
        },
        source="user",
        unique_id=TEST_DEVICE_SN,
    )

@pytest.fixture
def mock_solarman(device_fixture: str) -> Generator[AsyncMock]:
    """Mock a solarman client."""
    with (
        patch(
            "homeassistant.components.solarman.Solarman",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.solarman.config_flow.Solarman.get_config",
            new_callable=AsyncMock,
            return_value=load_json_object_fixture(f"{device_fixture}/config.json", DOMAIN)
        )
    ):
        client = mock_client.return_value
        client.get_config.return_value = load_json_object_fixture(f"{device_fixture}/config.json", DOMAIN)
        client.fetch_data.return_value = load_json_object_fixture(f"{device_fixture}/data.json", DOMAIN)
        yield client


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry
) -> None:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

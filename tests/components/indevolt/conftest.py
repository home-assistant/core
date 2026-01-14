"""Setup the Indevolt test environment."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.indevolt.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_HOST = "192.168.1.100"
TEST_PORT = 8080
TEST_DEVICE_SN_GEN1 = "BK1600-12345678"
TEST_DEVICE_SN_GEN2 = "SolidFlex2000-87654321"
TEST_FW_VERSION = "1.2.3"

# Map device fixture names to generation and fixture files
DEVICE_MAPPING = {
    1: {
        "device": "BK1600",
        "generation": 1,
        "fixture": "gen_1.json",
        "sn": TEST_DEVICE_SN_GEN1,
    },
    2: {
        "device": "CMS-SF2000",
        "generation": 2,
        "fixture": "gen_2.json",
        "sn": TEST_DEVICE_SN_GEN2,
    },
}


@pytest.fixture
def generation(request: pytest.FixtureRequest) -> int:
    """Return the device generation."""
    return request.param


@pytest.fixture
def mock_config_entry(generation: int) -> MockConfigEntry:
    """Return the default mocked config entry."""
    device_info = DEVICE_MAPPING[generation]
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{device_info['device']} ({TEST_HOST})",
        version=1,
        entry_id=f"indevolt_test_gen{generation}",
        data={
            "host": TEST_HOST,
            "sn": device_info["sn"],
            "device_model": device_info["device"],
            "generation": device_info["generation"],
        },
        source="user",
        unique_id=device_info["sn"],
    )


@pytest.fixture
def mock_indevolt(generation: int) -> Generator[AsyncMock]:
    """Mock an IndevoltAPI client."""
    device_info = DEVICE_MAPPING[generation]
    fixture_data = load_json_object_fixture(device_info["fixture"], DOMAIN)

    with (
        patch(
            "homeassistant.components.indevolt.coordinator.IndevoltAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.indevolt.config_flow.IndevoltAPI",
            autospec=True,
        ) as mock_config_flow_client,
    ):
        # Mock coordinator API (get_data)
        client = mock_client.return_value
        client.fetch_data.return_value = fixture_data
        client.get_config.return_value = {
            "device": {
                "sn": device_info["sn"],
                "type": device_info["device"],
                "generation": device_info["generation"],
                "fw": TEST_FW_VERSION,
            }
        }

        # Mock config flow API (get_config)
        config_flow_client = mock_config_flow_client.return_value
        config_flow_client.get_config.return_value = {
            "device": {
                "sn": device_info["sn"],
                "type": device_info["device"],
                "generation": device_info["generation"],
                "fw": TEST_FW_VERSION,
            }
        }

        yield client


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

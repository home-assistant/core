from unittest.mock import AsyncMock, patch
from collections.abc import Generator

import pytest

from homeassistant.core import HomeAssistant

from homeassistant.components.indevolt.const import DOMAIN

from tests.common import MockConfigEntry, load_json_object_fixture


TEST_HOST = "192.168.1.100"
TEST_PORT = 8080
TEST_SCAN_INTERVAL = 30
TEST_DEVICE_SN = "SN1234567890"
TEST_FW_VERSION = "1.2.3"
TEST_MODEL = "SolidFlex/PowerFlex2000"

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
            "scan_interval": TEST_SCAN_INTERVAL,
            "sn": TEST_DEVICE_SN,
            "fw_version": TEST_FW_VERSION,
            "model": device_fixture,
        },
        source="user",
        unique_id=f"{device_fixture}_{TEST_DEVICE_SN}",
    )

@pytest.fixture
def mock_indevolt(device_fixture: str) -> Generator[AsyncMock]:
    """Mock a indevolt client."""
    with (
        patch(
            "homeassistant.components.indevolt.coordinator.Indevolt",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.indevolt.config_flow.Indevolt.fetch_data",
            new_callable=AsyncMock,
            return_value={"0": TEST_DEVICE_SN}
        )
    ):
        client = mock_client.return_value
        client.fetch_all_data.return_value = load_json_object_fixture(f"{device_fixture.replace("/", "_")}/data.json", DOMAIN)
        yield client


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry
) -> None:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

"""Fixtures for WaterFurnace integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from waterfurnace.waterfurnace import WFGateway, WFReading

from homeassistant.components.waterfurnace.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.waterfurnace.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_waterfurnace_client() -> Generator[Mock]:
    """Mock WaterFurnace client."""
    with (
        patch(
            "homeassistant.components.waterfurnace.config_flow.WaterFurnace",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.waterfurnace.WaterFurnace",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.gwid = "TEST_GWID_12345"

        gateway_data = {
            "gwid": "TEST_GWID_12345",
            "description": "Test WaterFurnace Device",
            "awlabctypedesc": "Test ABC Type",
        }
        client.devices = [WFGateway(gateway_data)]

        device_data = WFReading(load_json_object_fixture("device_data.json", DOMAIN))
        client.read.return_value = device_data
        client.read_with_retry.return_value = device_data

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="WaterFurnace test_user",
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
        unique_id="TEST_GWID_12345",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> MockConfigEntry:
    """Set up the WaterFurnace integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry

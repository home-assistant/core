"""Fixtures for WaterFurnace integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from waterfurnace.waterfurnace import WaterFurnace, WFGateway, WFReading

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
        client.account_id = "test_account_id"

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
def mock_waterfurnace_client_multi_device() -> Generator[Mock]:
    """Mock WaterFurnace client with multiple devices."""
    gateway_data_1 = {
        "gwid": "TEST_GWID_12345",
        "description": "Test WaterFurnace Device 1",
        "awlabctypedesc": "Test ABC Type 1",
    }
    gateway_data_2 = {
        "gwid": "TEST_GWID_67890",
        "description": "Test WaterFurnace Device 2",
        "awlabctypedesc": "Test ABC Type 2",
    }

    device_data = WFReading(load_json_object_fixture("device_data.json", DOMAIN))

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
        instances: list[Mock] = []
        for gwid_data in (gateway_data_1, gateway_data_2):
            client = Mock(spec=WaterFurnace)
            client.gwid = gwid_data["gwid"]
            client.account_id = "test_account_id"
            client.devices = [WFGateway(gateway_data_1), WFGateway(gateway_data_2)]
            client.read.return_value = device_data
            client.read_with_retry.return_value = device_data
            instances.append(client)

        mock_client.side_effect = lambda username, password, device=0: instances[device]
        yield instances[0]


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
        unique_id="test_account_id",
        version=1,
        minor_version=2,
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

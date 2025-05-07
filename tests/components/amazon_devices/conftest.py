"""Amazon Devices tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aioamazondevices import AmazonDevice
import pytest

from homeassistant.components.amazon_devices.const import CONF_LOGIN_DATA, DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.amazon_devices.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_amazon_devices_client() -> Generator[AsyncMock]:
    """Mock an Amazon Devices client."""
    with (
        patch(
            "homeassistant.components.amazon_devices.coordinator.AmazonEchoApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.amazon_devices.config_flow.AmazonEchoApi",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login_mode_interactive.return_value = {
            "customer_info": {"user_id": "test"},
        }
        client.get_devices_data.return_value = {
            "test": AmazonDevice(
                account_name="test",
                capabilities=["cook"],
                device_family="mine",
                device_type="echo",
                device_owner_customer_id="test",
                device_cluster_members=["test"],
                online=True,
                serial_number="test",
                software_version="test",
                do_not_disturb=False,
                response_style=None,
                bluetooth_state=True,
            )
        }
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            CONF_COUNTRY: "IT",
            CONF_USERNAME: "test",
            CONF_PASSWORD: "test",
            CONF_LOGIN_DATA: {"test": "test"},
        },
        unique_id="test",
    )

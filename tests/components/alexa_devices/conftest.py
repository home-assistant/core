"""Alexa Devices tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aioamazondevices.api import AmazonDevice, AmazonDeviceSensor
from aioamazondevices.const import DEVICE_TYPE_TO_MODEL
import pytest

from homeassistant.components.alexa_devices.const import CONF_LOGIN_DATA, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import TEST_PASSWORD, TEST_SERIAL_NUMBER, TEST_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.alexa_devices.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_amazon_devices_client() -> Generator[AsyncMock]:
    """Mock an Alexa Devices client."""
    with (
        patch(
            "homeassistant.components.alexa_devices.coordinator.AmazonEchoApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.alexa_devices.config_flow.AmazonEchoApi",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login_mode_interactive.return_value = {
            "customer_info": {"user_id": TEST_USERNAME},
        }
        client.get_devices_data.return_value = {
            TEST_SERIAL_NUMBER: AmazonDevice(
                account_name="Echo Test",
                capabilities=["AUDIO_PLAYER", "MICROPHONE"],
                device_family="mine",
                device_type="echo",
                device_owner_customer_id="amazon_ower_id",
                device_cluster_members=[TEST_SERIAL_NUMBER],
                online=True,
                serial_number=TEST_SERIAL_NUMBER,
                software_version="echo_test_software_version",
                do_not_disturb=False,
                response_style=None,
                bluetooth_state=True,
                entity_id="11111111-2222-3333-4444-555555555555",
                appliance_id="G1234567890123456789012345678A",
                sensors={
                    "temperature": AmazonDeviceSensor(
                        name="temperature", value="22.5", scale="CELSIUS"
                    )
                },
            )
        }
        client.get_model_details = lambda device: DEVICE_TYPE_TO_MODEL.get(
            device.device_type
        )
        client.send_sound_notification = AsyncMock()
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Amazon Test Account",
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_LOGIN_DATA: {"session": "test-session"},
        },
        unique_id=TEST_USERNAME,
        version=1,
        minor_version=2,
    )

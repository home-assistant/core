"""Alexa Devices tests configuration."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from aioamazondevices.const import DEVICE_TYPE_TO_MODEL
import pytest

from homeassistant.components.alexa_devices.const import (
    CONF_LOGIN_DATA,
    CONF_SITE,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import TEST_DEVICE_1, TEST_DEVICE_1_SN, TEST_PASSWORD, TEST_USERNAME

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
            TEST_DEVICE_1_SN: deepcopy(TEST_DEVICE_1)
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
            CONF_LOGIN_DATA: {
                "session": "test-session",
                CONF_SITE: "https://www.amazon.com",
            },
        },
        unique_id=TEST_USERNAME,
        version=1,
        minor_version=3,
    )

"""Fixtures for iotty integration tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from iottycloud.device import Device
from iottycloud.verbs import LS_DEVICE_TYPE_UID
import pytest

from homeassistant import setup
from homeassistant.components.iotty import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry

CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secret"
REDIRECT_URI = "https://example.com/auth/external/callback"


@pytest.fixture
async def oauth_impl(hass: HomeAssistant):
    """Local implementation."""
    assert await setup.async_setup_component(hass, "auth", {})
    return config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass, DOMAIN, "client_id", "client_secret", "authorize_url", "token_url"
    )


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="IOTTY00001",
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PORT: 9123,
        },
        unique_id="IOTTY00001",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.iotty.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_iotty() -> Generator[None, MagicMock, None]:
    """Return a mocked IottyProxy."""
    with patch(
        "homeassistant.components.iotty.api.IottyProxy", autospec=True
    ) as iotty_mock:
        yield iotty_mock


@pytest.fixture
def mock_devices() -> Generator[None, MagicMock, None]:
    """Fixture for two LS Devices."""
    return [
        Device(
            "TestDevice0", "TEST_SERIAL_0", LS_DEVICE_TYPE_UID, "[TEST] Device Name 0"
        ),
        Device(
            "TestDevice1", "TEST_SERIAL_1", LS_DEVICE_TYPE_UID, "[TEST] Device Name 1"
        ),
    ]

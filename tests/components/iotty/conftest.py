"""Fixtures for iotty integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientSession
from iottycloud.device import Device
from iottycloud.lightswitch import LightSwitch
from iottycloud.verbs import LS_DEVICE_TYPE_UID, RESULT, STATUS, STATUS_OFF, STATUS_ON
import pytest

from homeassistant import setup
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, mock_aiohttp_client

CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secret"
REDIRECT_URI = "https://example.com/auth/external/callback"

test_devices = [
    Device("TestDevice0", "TEST_SERIAL_0", LS_DEVICE_TYPE_UID, "[TEST] Device Name 0"),
    Device("TestDevice1", "TEST_SERIAL_1", LS_DEVICE_TYPE_UID, "[TEST] Device Name 1"),
]


ls_0 = LightSwitch(
    "TestLS", "TEST_SERIAL_0", LS_DEVICE_TYPE_UID, "[TEST] Light switch 0"
)
ls_1 = LightSwitch(
    "TestLS1", "TEST_SERIAL_1", LS_DEVICE_TYPE_UID, "[TEST] Light switch 1"
)
ls_2 = LightSwitch(
    "TestLS2", "TEST_SERIAL_2", LS_DEVICE_TYPE_UID, "[TEST] Light switch 2"
)

test_ls = [ls_0, ls_1]

test_ls_one_removed = [ls_0]

test_ls_one_added = [
    ls_0,
    ls_1,
    ls_2,
]


@pytest.fixture
async def local_oauth_impl(hass: HomeAssistant):
    """Local implementation."""
    assert await setup.async_setup_component(hass, "auth", {})
    return config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass, DOMAIN, "client_id", "client_secret", "authorize_url", "https://token.url"
    )


@pytest.fixture
def aiohttp_client_session() -> None:
    """AIOHTTP client session."""
    return ClientSession


@pytest.fixture
def mock_aioclient() -> Generator[AiohttpClientMocker]:
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="IOTTY00001",
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "REFRESH_TOKEN",
                "access_token": "ACCESS_TOKEN_1",
                "expires_in": 10,
                "expires_at": 0,
                "token_type": "bearer",
                "random_other_data": "should_stay",
            },
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PORT: 9123,
        },
        unique_id="IOTTY00001",
    )


@pytest.fixture
def mock_config_entries_async_forward_entry_setup() -> Generator[AsyncMock]:
    """Mock async_forward_entry_setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
    ) as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.iotty.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_iotty() -> Generator[MagicMock]:
    """Mock IottyProxy."""
    with patch(
        "homeassistant.components.iotty.api.IottyProxy", autospec=True
    ) as iotty_mock:
        yield iotty_mock


@pytest.fixture
def mock_coordinator() -> Generator[MagicMock]:
    """Mock IottyDataUpdateCoordinator."""
    with patch(
        "homeassistant.components.iotty.coordinator.IottyDataUpdateCoordinator",
        autospec=True,
    ) as coordinator_mock:
        yield coordinator_mock


@pytest.fixture
def mock_get_devices_nodevices() -> Generator[AsyncMock]:
    """Mock for get_devices, returning two objects."""

    with patch("iottycloud.cloudapi.CloudApi.get_devices") as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_get_devices_twolightswitches() -> Generator[AsyncMock]:
    """Mock for get_devices, returning two objects."""

    with patch(
        "iottycloud.cloudapi.CloudApi.get_devices", return_value=test_ls
    ) as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_command_fn() -> Generator[AsyncMock]:
    """Mock for command."""

    with patch("iottycloud.cloudapi.CloudApi.command", return_value=None) as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_get_status_filled_off() -> Generator[AsyncMock]:
    """Mock setting up a get_status."""

    retval = {RESULT: {STATUS: STATUS_OFF}}
    with patch(
        "iottycloud.cloudapi.CloudApi.get_status", return_value=retval
    ) as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_get_status_filled() -> Generator[AsyncMock]:
    """Mock setting up a get_status."""

    retval = {RESULT: {STATUS: STATUS_ON}}
    with patch(
        "iottycloud.cloudapi.CloudApi.get_status", return_value=retval
    ) as mock_fn:
        yield mock_fn

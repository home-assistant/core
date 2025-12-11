"""Configuration for Eufy Security tests."""

from collections.abc import Generator
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.eufy_security.const import (
    CONF_API_BASE,
    CONF_PRIVATE_KEY,
    CONF_SERVER_PUBLIC_KEY,
    CONF_TOKEN,
    CONF_TOKEN_EXPIRATION,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.eufy_security.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_camera() -> MagicMock:
    """Create a mock camera."""
    camera = MagicMock()
    camera.serial = "T1234567890"
    camera.station_serial = "T0987654321"
    camera.name = "Front Door Camera"
    camera.model = "eufyCam 2"
    camera.hardware_version = "2.2"
    camera.software_version = "2.0.7.6"
    camera.ip_address = "192.168.1.100"
    camera.last_camera_image_url = "https://example.com/image.jpg"
    camera.rtsp_username = None
    camera.rtsp_password = None
    camera.async_start_stream = AsyncMock(return_value="rtsp://example.com/stream")
    camera.async_stop_stream = AsyncMock()
    return camera


@pytest.fixture
def mock_station() -> MagicMock:
    """Create a mock station."""
    station = MagicMock()
    station.serial = "T0987654321"
    station.name = "Home Base"
    station.model = "HomeBase 2"
    return station


@pytest.fixture
def mock_eufy_api(
    mock_camera: MagicMock, mock_station: MagicMock
) -> Generator[MagicMock]:
    """Mock the Eufy Security API for integration setup."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.cameras = {mock_camera.serial: mock_camera}
        api.stations = {mock_station.serial: mock_station}
        api.async_authenticate = AsyncMock()
        api.async_update_device_info = AsyncMock()
        api.token = "test-token"
        api.token_expiration = datetime.now() + timedelta(days=1)
        api.api_base = "https://mysecurity.eufylife.com"
        api.get_crypto_state = MagicMock(
            return_value={
                "private_key": "0" * 64,
                "server_public_key": "0" * 64,
            }
        )
        api.restore_crypto_state = MagicMock(return_value=False)
        api.set_token = MagicMock()

        mock_api_class.return_value = api
        yield api


@pytest.fixture
def mock_config_flow_api(
    mock_camera: MagicMock, mock_station: MagicMock
) -> Generator[MagicMock]:
    """Mock the async_login function for config flow tests."""
    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login"
    ) as mock_login:
        api = MagicMock()
        api.cameras = {mock_camera.serial: mock_camera}
        api.stations = {mock_station.serial: mock_station}
        api.token = "test-token"
        api.token_expiration = datetime.now() + timedelta(days=1)
        api.api_base = "https://mysecurity.eufylife.com"
        api.get_crypto_state = MagicMock(
            return_value={
                "private_key": "0" * 64,
                "server_public_key": "0" * 64,
            }
        )

        mock_login.return_value = api
        yield api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: "stored-token",
            CONF_TOKEN_EXPIRATION: (datetime.now() + timedelta(days=1)).isoformat(),
            CONF_API_BASE: "https://mysecurity.eufylife.com",
            CONF_PRIVATE_KEY: "0" * 64,
            CONF_SERVER_PUBLIC_KEY: "0" * 64,
        },
        unique_id="test@example.com",
        version=1,
        minor_version=1,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eufy_api: MagicMock,
) -> MockConfigEntry:
    """Set up the Eufy Security integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

"""Test configuration for Hisense AC Plugin."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.application_credentials import ApplicationCredentials
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from custom_components.hisense_connectlife.const import DOMAIN


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_update_entry = AsyncMock()
    hass.config_entries.async_reload = AsyncMock()
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = "Hisense AC Plugin"
    entry.data = {
        "auth_implementation": DOMAIN,
        "implementation": DOMAIN,
        "token": {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "expires_at": 1234567890,
        },
    }
    entry.options = {}
    entry.pref_disable_new_entities = False
    entry.pref_disable_polling = False
    entry.state = MagicMock()
    entry.state.value = "loaded"
    entry.source = "user"
    entry.version = 1
    return entry


@pytest.fixture
def mock_legacy_config_entry():
    """Mock legacy config entry without Application Credentials."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = "Hisense AC Plugin"
    entry.data = {
        "token": {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "expires_at": 1234567890,
        },
    }
    entry.options = {}
    entry.pref_disable_new_entities = False
    entry.pref_disable_polling = False
    entry.state = MagicMock()
    entry.state.value = "loaded"
    entry.source = "user"
    entry.version = 1
    return entry


@pytest.fixture
def mock_device_data():
    """Mock device data from API."""
    return {
        "deviceId": "test_device_1",
        "puid": "test_puid_1",
        "deviceName": "Test AC Unit",
        "deviceTypeCode": "009",
        "deviceFeatureCode": "199",
        "deviceFeatureName": "Split Air Conditioner",
        "statusList": {
            "t_power": "1",
            "t_work_mode": "cool",
            "t_temp": "25",
            "f_temp_in": "24",
        },
        "failedData": [],
        "staticData": {},
    }


@pytest.fixture
def mock_api_response():
    """Mock API response."""
    return {
        "resultCode": 0,
        "msg": "success",
        "deviceList": [
            {
                "deviceId": "test_device_1",
                "puid": "test_puid_1",
                "deviceName": "Test AC Unit",
                "deviceTypeCode": "009",
                "deviceFeatureCode": "199",
                "deviceFeatureName": "Split Air Conditioner",
                "statusList": {
                    "t_power": "1",
                    "t_work_mode": "cool",
                    "t_temp": "25",
                    "f_temp_in": "24",
                },
            }
        ],
    }


@pytest.fixture
def mock_oauth2_session():
    """Mock OAuth2 session."""
    session = AsyncMock()
    session.async_ensure_token_valid = AsyncMock()
    session.async_get_access_token = AsyncMock(return_value="test_access_token")
    session.close = AsyncMock()
    session.session = AsyncMock()
    return session


@pytest.fixture
def mock_oauth2_implementation():
    """Mock OAuth2 implementation."""
    implementation = MagicMock()
    implementation.async_generate_authorize_url = AsyncMock(
        return_value="https://oauth.hijuconn.com/login?client_id=test&response_type=code"
    )
    implementation.async_refresh_token = AsyncMock(
        return_value={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }
    )
    return implementation


@pytest.fixture
def mock_application_credentials():
    """Mock Application Credentials."""
    with patch("custom_components.hisense_connectlife.auth.config_entry_oauth2_flow") as mock_oauth2:
        mock_session = AsyncMock()
        mock_session.async_ensure_token_valid = AsyncMock(
            return_value={
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 3600,
            }
        )
        mock_oauth2.OAuth2Session.return_value = mock_session
        mock_oauth2.async_get_config_entry_implementation = AsyncMock()
        yield mock_oauth2


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    websocket = AsyncMock()
    websocket.async_connect = AsyncMock()
    websocket.async_disconnect = AsyncMock()
    websocket.connected = True
    return websocket


@pytest.fixture
def mock_coordinator():
    """Mock data update coordinator."""
    coordinator = AsyncMock()
    coordinator.api_client = AsyncMock()
    coordinator._devices = {}
    coordinator.data = {}
    coordinator.last_update_success = True
    coordinator.last_update_time = None
    coordinator.update_interval = None
    coordinator.async_setup = AsyncMock(return_value=True)
    coordinator.async_refresh = AsyncMock()
    coordinator.async_set_updated_data = AsyncMock()
    coordinator.get_device = MagicMock(return_value=None)
    coordinator.async_unload = AsyncMock()
    return coordinator


@pytest.fixture
def mock_api_client():
    """Mock API client."""
    client = AsyncMock()
    client.async_get_devices = AsyncMock(return_value={})
    client.async_control_device = AsyncMock(return_value={"success": True})
    client.async_cleanup = AsyncMock()
    client.oauth_session = AsyncMock()
    client.oauth_session.close = AsyncMock()
    return client


@pytest.fixture
def mock_device_info():
    """Mock device info."""
    device = MagicMock()
    device.device_id = "test_device_1"
    device.puid = "test_puid_1"
    device.name = "Test AC Unit"
    device.type_code = "009"
    device.feature_code = "199"
    device.feature_name = "Split Air Conditioner"
    device.status = {
        "t_power": "1",
        "t_work_mode": "cool",
        "t_temp": "25",
        "f_temp_in": "24",
    }
    device.failed_data = []
    device.static_data = {}
    device.get_device_type = MagicMock(return_value=("009", "199"))
    device.to_dict = MagicMock(
        return_value={
            "deviceId": "test_device_1",
            "puid": "test_puid_1",
            "deviceName": "Test AC Unit",
            "deviceTypeCode": "009",
            "deviceFeatureCode": "199",
            "deviceFeatureName": "Split Air Conditioner",
            "statusList": {
                "t_power": "1",
                "t_work_mode": "cool",
                "t_temp": "25",
                "f_temp_in": "24",
            },
            "failedData": [],
            "staticData": {},
        }
    )
    device.debug_info = MagicMock(return_value="Device debug info")
    return device

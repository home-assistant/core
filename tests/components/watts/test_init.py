"""Test the Watts Vision integration initialization."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from visionpluspython.exceptions import (
    WattsVisionAuthError,
    WattsVisionConnectionError,
    WattsVisionDeviceError,
    WattsVisionError,
    WattsVisionTimeoutError,
)
from visionpluspython.models import create_device_from_data

from homeassistant.components.watts.const import (
    DISCOVERY_INTERVAL_MINUTES,
    DOMAIN,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_watts_client.discover_devices.assert_called_once()

    unload_result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert unload_result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup with authentication failure."""
    config_entry = MockConfigEntry(
        domain="watts",
        unique_id="test-device-id",
        data={
            "device_id": "test-device-id",
            "auth_implementation": "watts",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 0,  # Expired token to force refresh
            },
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, status=401)

    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup when network is temporarily unavailable."""
    config_entry = MockConfigEntry(
        domain="watts",
        unique_id="test-device-id",
        data={
            "device_id": "test-device-id",
            "auth_implementation": "watts",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 0,  # Expired token to force refresh
            },
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, exc=ClientError("Connection timeout"))

    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_hub_coordinator_update_failed(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup when hub coordinator update fails."""

    # Make discover_devices fail
    mock_watts_client.discover_devices.side_effect = ConnectionError("API error")

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_entry_server_error_5xx(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup when server returns error."""
    config_entry = MockConfigEntry(
        domain="watts",
        unique_id="test-device-id",
        data={
            "device_id": "test-device-id",
            "auth_implementation": "watts",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 0,  # Expired token to force refresh
            },
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.post(OAUTH2_TOKEN, status=500)

    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (WattsVisionAuthError("Auth failed"), ConfigEntryState.SETUP_ERROR),
        (WattsVisionConnectionError("Connection lost"), ConfigEntryState.SETUP_RETRY),
        (WattsVisionTimeoutError("Request timeout"), ConfigEntryState.SETUP_RETRY),
        (WattsVisionDeviceError("Device error"), ConfigEntryState.SETUP_RETRY),
        (WattsVisionError("API error"), ConfigEntryState.SETUP_RETRY),
        (ValueError("Value error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_discover_devices_errors(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup errors during device discovery."""
    mock_watts_client.discover_devices.side_effect = exception

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is expected_state


async def test_dynamic_device_creation(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are created dynamically."""
    await setup_integration(hass, mock_config_entry)

    assert device_registry.async_get_device(identifiers={(DOMAIN, "thermostat_123")})
    assert device_registry.async_get_device(identifiers={(DOMAIN, "thermostat_456")})
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, "thermostat_789")})
        is None
    )

    new_device_data = {
        "deviceId": "thermostat_789",
        "deviceName": "Kitchen Thermostat",
        "deviceType": "thermostat",
        "interface": "homeassistant.components.THERMOSTAT",
        "roomName": "Kitchen",
        "isOnline": True,
        "currentTemperature": 21.0,
        "setpoint": 20.0,
        "thermostatMode": "Comfort",
        "minAllowedTemperature": 5.0,
        "maxAllowedTemperature": 30.0,
        "temperatureUnit": "C",
        "availableThermostatModes": ["Program", "Eco", "Comfort", "Off"],
    }
    new_device = create_device_from_data(new_device_data)

    current_devices = list(mock_watts_client.discover_devices.return_value)
    mock_watts_client.discover_devices.return_value = [*current_devices, new_device]

    freezer.tick(timedelta(minutes=DISCOVERY_INTERVAL_MINUTES))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    new_device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "thermostat_789")}
    )
    assert new_device_entry is not None
    assert new_device_entry.name == "Kitchen Thermostat"

    state = hass.states.get("climate.kitchen_thermostat")
    assert state is not None


async def test_stale_device_removal(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test stale devices are removed dynamically."""
    await setup_integration(hass, mock_config_entry)

    device_123 = device_registry.async_get_device(
        identifiers={(DOMAIN, "thermostat_123")}
    )
    device_456 = device_registry.async_get_device(
        identifiers={(DOMAIN, "thermostat_456")}
    )
    assert device_123 is not None
    assert device_456 is not None

    current_devices = list(mock_watts_client.discover_devices.return_value)
    # remove thermostat_456
    mock_watts_client.discover_devices.return_value = [
        d for d in current_devices if d.device_id != "thermostat_456"
    ]

    freezer.tick(timedelta(minutes=DISCOVERY_INTERVAL_MINUTES))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify thermostat_456 has been removed
    device_456_after_removal = device_registry.async_get_device(
        identifiers={(DOMAIN, "thermostat_456")}
    )
    assert device_456_after_removal is None

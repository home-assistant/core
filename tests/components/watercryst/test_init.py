"""Tests for the WATERCryst integration setup."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import HTTPStatusError, Request, RequestError, Response
import pytest

from homeassistant.components.watercryst.const import CONF_BSN, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)

from tests.common import MockConfigEntry

MOCK_API_KEY = "test-api-key"
MOCK_BSN = "1234567890"
MOCK_BLE_MAC = "112233445566"
MOCK_SYSTEM_MAC = "aa:bb:cc:dd:ee:ff"


def _device_info(**overrides: object) -> SimpleNamespace:
    """Create mock WATERCryst device information."""
    values: dict[str, object] = {
        "biocat_serial": MOCK_BSN,
        "system_mac_address": MOCK_SYSTEM_MAC,
        "ble_mac_address": MOCK_BLE_MAC,
        "line": "BIOCAT",
        "series": "KS 3000",
        "device_type_number": "1234",
        "name": "BIOCAT utility room",
        "current_firmware_version": "1.2.3",
        "current_hardware_version": "4.5.6",
        "has_flow_rate_sensor": True,
        "has_leakage_protection_system": True,
        "has_pressure_sensor": True,
        "has_temperature_sensor": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _state(*, online: bool = True) -> SimpleNamespace:
    """Create a mock WATERCryst state."""
    return SimpleNamespace(online=online)


def _http_status_error(status_code: int) -> HTTPStatusError:
    """Create an HTTP status error with a complete request and response."""
    request = Request("GET", "https://api.watercryst.com/device")
    response = Response(status_code, request=request)
    return HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and register a WATERCryst config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BIOCAT utility room",
        data={CONF_BSN: MOCK_BSN, CONF_API_KEY: MOCK_API_KEY},
        unique_id=MOCK_BSN,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_watercryst_client() -> Generator[MagicMock]:
    """Mock the WATERCryst API client."""
    with patch(
        "homeassistant.components.watercryst.AsyncApiClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.get_device_info = AsyncMock(return_value=_device_info())
        client.get_state = AsyncMock(return_value=_state())
        yield client


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercryst_client: MagicMock,
) -> None:
    """Test config-entry setup, runtime data, device metadata, and unload."""
    with (
        patch(
            "homeassistant.components.watercryst.MeasurementsUpdateCoordinator",
            autospec=True,
        ) as measurements_class,
        patch(
            "homeassistant.components.watercryst.StateUpdateCoordinator",
            autospec=True,
        ) as state_class,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ) as forward_setups,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new_callable=AsyncMock,
            return_value=True,
        ) as unload_platforms,
    ):
        measurements = measurements_class.return_value
        state = state_class.return_value
        measurements.async_config_entry_first_refresh = AsyncMock()
        state.async_config_entry_first_refresh = AsyncMock()

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED

        runtime_data = config_entry.runtime_data
        assert runtime_data.bsn == MOCK_BSN
        assert runtime_data.has_flow_rate_sensor
        assert runtime_data.has_leakage_protection_system
        assert runtime_data.has_pressure_sensor
        assert runtime_data.has_temperature_sensor
        assert runtime_data.client is mock_watercryst_client
        assert runtime_data.measurements is measurements
        assert runtime_data.state is state
        assert runtime_data.device_info == DeviceInfo(
            identifiers={(DOMAIN, MOCK_BSN)},
            connections={
                (CONNECTION_NETWORK_MAC, MOCK_SYSTEM_MAC),
                (CONNECTION_BLUETOOTH, format_mac(MOCK_BLE_MAC)),
            },
            manufacturer="WATERCryst",
            model="BIOCAT KS 3000",
            model_id="1234",
            name="BIOCAT utility room",
            serial_number=MOCK_BSN,
            sw_version="1.2.3",
            hw_version="4.5.6",
            configuration_url=f"https://app.watercryst.com/devices/{MOCK_BSN}",
        )

        mock_watercryst_client.get_device_info.assert_awaited_once_with()
        mock_watercryst_client.get_state.assert_awaited_once_with()
        measurements.async_config_entry_first_refresh.assert_awaited_once_with()
        state.async_config_entry_first_refresh.assert_awaited_once_with()
        forward_setups.assert_awaited_once_with(config_entry, [Platform.SENSOR])

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED
        unload_platforms.assert_awaited_once_with(config_entry, [Platform.SENSOR])


async def test_setup_invalid_authentication(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercryst_client: MagicMock,
) -> None:
    """Test a 401 response fails setup as an authentication error."""
    mock_watercryst_client.get_device_info.side_effect = _http_status_error(401)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "Invalid authentication"


async def test_setup_offline_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercryst_client: MagicMock,
) -> None:
    """Test an offline device schedules a setup retry."""
    mock_watercryst_client.get_state.return_value = _state(online=False)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.reason == "Device is offline"


async def test_setup_transport_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercryst_client: MagicMock,
) -> None:
    """Test a transport error schedules a setup retry."""
    request = Request("GET", "https://api.watercryst.com/device")
    mock_watercryst_client.get_device_info.side_effect = RequestError(
        "Connection failed", request=request
    )

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.reason == "Temporary API error"


@pytest.mark.parametrize("status_code", [500, 503])
async def test_setup_server_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercryst_client: MagicMock,
    status_code: int,
) -> None:
    """Test server errors schedule a setup retry."""
    mock_watercryst_client.get_device_info.side_effect = _http_status_error(status_code)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.reason == "Temporary API error"


async def test_setup_serial_number_mismatch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercryst_client: MagicMock,
) -> None:
    """Test a device response for another BIOCAT fails authentication."""
    mock_watercryst_client.get_device_info.return_value = _device_info(
        biocat_serial="0987654321"
    )

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "BIOCAT serial number mismatch"
    mock_watercryst_client.get_state.assert_not_awaited()


async def test_setup_api_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercryst_client: MagicMock,
) -> None:
    """Test a disabled API fails setup without retrying."""
    mock_watercryst_client.get_device_info.side_effect = _http_status_error(403)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "API disabled"


async def test_setup_unexpected_http_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercryst_client: MagicMock,
) -> None:
    """Test an unclassified client response fails setup."""
    mock_watercryst_client.get_device_info.side_effect = _http_status_error(400)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "Unexpected error"

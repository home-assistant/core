"""Tests for the LoJack coordinator."""

from datetime import UTC, datetime, timedelta
from email.utils import formatdate
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import MockApiError, MockAuthenticationError
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry


class MockException(Exception):
    """Mock exception with optional headers."""

    def __init__(self, message: str, status: int | None = None, headers: dict | None = None):
        """Initialize mock exception."""
        super().__init__(message)
        self.status = status
        self.headers = headers or {}


class MockResponse:
    """Mock response object."""

    def __init__(self, headers: dict | None = None):
        """Initialize mock response."""
        self.headers = headers or {}


async def test_coordinator_fetch_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test coordinator fetches data successfully."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is not None
    assert TEST_DEVICE_ID in coordinator.data


async def test_coordinator_auth_error_refresh_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_location: MagicMock,
) -> None:
    """Test coordinator handles token refresh successfully."""
    mock_device.get_location = AsyncMock(return_value=mock_location)

    # Initial client that will work during setup but fail later
    old_client = AsyncMock()
    old_client.list_devices = AsyncMock(return_value=[mock_device])
    old_client.close = AsyncMock()

    # New client after refresh
    new_client = AsyncMock()
    new_client.list_devices = AsyncMock(return_value=[mock_device])
    new_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data
        assert coordinator.client is old_client

        # Now make the current client fail with auth error and mock new client creation
        old_client.list_devices = AsyncMock(side_effect=MockAuthenticationError("Token expired"))

        with patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=new_client,
        ):
            await coordinator.async_refresh()

        # Verify new client is installed and old one was closed
        assert coordinator.client is new_client
        old_client.close.assert_called_once()
        assert coordinator.data is not None


async def test_coordinator_auth_error_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles token refresh failure."""
    old_client = AsyncMock()
    old_client.list_devices = AsyncMock(side_effect=MockAuthenticationError("Token expired"))
    old_client.close = AsyncMock()

    new_client = AsyncMock()
    new_client.list_devices = AsyncMock(side_effect=MockAuthenticationError("Still invalid"))
    new_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            side_effect=[old_client, new_client],
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=new_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Coordinator setup will fail due to auth error
        assert mock_config_entry.state.name == "SETUP_ERROR"


async def test_coordinator_api_error_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles API error during token refresh."""
    old_client = AsyncMock()
    old_client.list_devices = AsyncMock(side_effect=MockAuthenticationError("Token expired"))
    old_client.close = AsyncMock()

    new_client = AsyncMock()
    new_client.list_devices = AsyncMock(side_effect=MockApiError("API error"))
    new_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            side_effect=[old_client, new_client],
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=new_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.AuthenticationError",
            MockAuthenticationError,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state.name == "SETUP_RETRY"


async def test_coordinator_rate_limit_429_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator detects rate limiting by status code."""
    old_client = AsyncMock()
    err = MockException("Rate limited", status=429)
    old_client.list_devices = AsyncMock(side_effect=err)
    old_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state.name == "SETUP_RETRY"


async def test_coordinator_rate_limit_429_string(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator detects rate limiting by error string."""
    old_client = AsyncMock()
    old_client.list_devices = AsyncMock(side_effect=MockApiError("Error 429: Too Many Requests"))
    old_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=old_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state.name == "SETUP_RETRY"


async def test_coordinator_rate_limit_with_retry_after_int(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_location: MagicMock,
) -> None:
    """Test coordinator respects Retry-After header with integer seconds."""
    mock_device.get_location = AsyncMock(return_value=mock_location)

    rate_limited_client = AsyncMock()
    err = MockException("Rate limited", status=429, headers={"Retry-After": "60"})
    rate_limited_client.list_devices = AsyncMock(side_effect=err)
    rate_limited_client.close = AsyncMock()

    normal_client = AsyncMock()
    normal_client.list_devices = AsyncMock(return_value=[mock_device])
    normal_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            side_effect=[rate_limited_client, normal_client],
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=rate_limited_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=normal_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state.name == "SETUP_RETRY"


async def test_coordinator_rate_limit_with_retry_after_http_date(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_location: MagicMock,
) -> None:
    """Test coordinator respects Retry-After header with HTTP date."""
    mock_device.get_location = AsyncMock(return_value=mock_location)

    # Create a date 60 seconds in the future
    future_time = datetime.now(tz=UTC) + timedelta(seconds=60)
    http_date = formatdate(timeval=future_time.timestamp(), localtime=False, usegmt=True)

    rate_limited_client = AsyncMock()
    err = MockException("Rate limited", status=429, headers={"Retry-After": http_date})
    rate_limited_client.list_devices = AsyncMock(side_effect=err)
    rate_limited_client.close = AsyncMock()

    normal_client = AsyncMock()
    normal_client.list_devices = AsyncMock(return_value=[mock_device])
    normal_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            side_effect=[rate_limited_client, normal_client],
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=rate_limited_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=normal_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state.name == "SETUP_RETRY"


async def test_coordinator_device_without_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles devices without ID."""
    device_no_id = MagicMock()
    device_no_id.id = None
    device_no_id.get_location = AsyncMock()

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[device_no_id])
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

        coordinator = mock_config_entry.runtime_data
        # Data should be empty since device has no ID
        assert len(coordinator.data or {}) == 0


async def test_coordinator_location_fetch_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test coordinator handles location fetch failures gracefully."""
    mock_device.get_location = AsyncMock(side_effect=Exception("Location unavailable"))

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

        coordinator = mock_config_entry.runtime_data
        assert TEST_DEVICE_ID in coordinator.data
        vehicle = coordinator.data[TEST_DEVICE_ID]
        # Location data should be None
        assert vehicle.latitude is None
        assert vehicle.longitude is None
        assert vehicle.accuracy is None


async def test_coordinator_safe_float_conversion(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test coordinator handles non-numeric location values."""
    location = MagicMock()
    location.latitude = "invalid"
    location.longitude = None
    location.accuracy = "also_invalid"
    location.heading = 123.456  # Valid
    location.address = "Test Address"
    location.timestamp = "2020-02-02T14:00:00Z"

    mock_device.get_location = AsyncMock(return_value=location)

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

        coordinator = mock_config_entry.runtime_data
        vehicle = coordinator.data[TEST_DEVICE_ID]
        assert vehicle.latitude is None  # Invalid string
        assert vehicle.longitude is None  # None
        assert vehicle.accuracy is None  # Invalid string
        assert vehicle.heading == 123.456  # Valid


async def test_coordinator_retry_after_invalid_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_location: MagicMock,
) -> None:
    """Test coordinator handles invalid Retry-After header values."""
    mock_device.get_location = AsyncMock(return_value=mock_location)

    rate_limited_client = AsyncMock()
    # Invalid Retry-After values
    err = MockException("Rate limited", status=429, headers={"Retry-After": "invalid-date"})
    rate_limited_client.list_devices = AsyncMock(side_effect=err)
    rate_limited_client.close = AsyncMock()

    normal_client = AsyncMock()
    normal_client.list_devices = AsyncMock(return_value=[mock_device])
    normal_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            side_effect=[rate_limited_client, normal_client],
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=rate_limited_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=normal_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state.name == "SETUP_RETRY"


async def test_coordinator_retry_after_with_response_object(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_location: MagicMock,
) -> None:
    """Test coordinator extracts Retry-After from response object."""
    mock_device.get_location = AsyncMock(return_value=mock_location)

    rate_limited_client = AsyncMock()
    err = MockException("Rate limited", status=429)
    err.response = MockResponse(headers={"Retry-After": "120"})
    rate_limited_client.list_devices = AsyncMock(side_effect=err)
    rate_limited_client.close = AsyncMock()

    normal_client = AsyncMock()
    normal_client.list_devices = AsyncMock(return_value=[mock_device])
    normal_client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            side_effect=[rate_limited_client, normal_client],
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=rate_limited_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=normal_client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state.name == "SETUP_RETRY"

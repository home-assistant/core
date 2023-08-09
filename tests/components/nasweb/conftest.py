"""Common fixtures for the NASweb tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nasweb.coordinator import NotificationCoordinator


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nasweb.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


BASE = "homeassistant.components.nasweb.config_flow"
WEBIO_API_CHECK_CONNECTION = f"{BASE}.WebioAPI.check_connection"
WEBIO_API_REFRESH_DEVICE_INFO = f"{BASE}.WebioAPI.refresh_device_info"
INITIALIZE_NOTIFICATION_COORDINATOR = f"{BASE}.initialize_notification_coordinator"
WEBIO_API_GET_SERIAL_NUMBER = f"{BASE}.WebioAPI.get_serial_number"
GET_HASS_ADDRESS_FROM_ENTRY = f"{BASE}.get_hass_address_from_entry"
WEBIO_API_STATUS_SUBSCRIPTION = f"{BASE}.WebioAPI.status_subscription"
NOTIFICATION_COORDINATOR_CHECK_CONNECTION = (
    f"{BASE}.NotificationCoordinator.check_connection"
)


@pytest.fixture
def validate_input_all_ok() -> Generator[dict[str, AsyncMock | MagicMock], None, None]:
    """Yield dictionary of mocked functions required for successful test_form execution."""
    with patch(
        WEBIO_API_CHECK_CONNECTION,
        return_value=True,
    ) as check_connection, patch(
        WEBIO_API_REFRESH_DEVICE_INFO,
        return_value=True,
    ) as refresh_device_info, patch(
        INITIALIZE_NOTIFICATION_COORDINATOR,
        return_value=NotificationCoordinator(),
    ) as initialize_coordinator, patch(
        WEBIO_API_GET_SERIAL_NUMBER,
        return_value="0011223344556677",
    ) as get_serial, patch(
        GET_HASS_ADDRESS_FROM_ENTRY,
        return_value="False:localhost:8123",
    ) as get_hass_address, patch(
        WEBIO_API_STATUS_SUBSCRIPTION,
        return_value=True,
    ) as status_subscription, patch(
        NOTIFICATION_COORDINATOR_CHECK_CONNECTION,
        return_value=True,
    ) as check_status_confirmation:
        yield {
            WEBIO_API_CHECK_CONNECTION: check_connection,
            WEBIO_API_REFRESH_DEVICE_INFO: refresh_device_info,
            INITIALIZE_NOTIFICATION_COORDINATOR: initialize_coordinator,
            WEBIO_API_GET_SERIAL_NUMBER: get_serial,
            GET_HASS_ADDRESS_FROM_ENTRY: get_hass_address,
            WEBIO_API_STATUS_SUBSCRIPTION: status_subscription,
            NOTIFICATION_COORDINATOR_CHECK_CONNECTION: check_status_confirmation,
        }

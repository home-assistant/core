"""Common fixtures for the NASweb tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nasweb.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


BASE_CONFIG_FLOW = "homeassistant.components.nasweb.config_flow."
BASE_NASWEB_DATA = "homeassistant.components.nasweb.nasweb_data."
BASE_COORDINATOR = "homeassistant.components.nasweb.coordinator."
TEST_SERIAL_NUMBER = "0011223344556677"


@pytest.fixture
def validate_input_all_ok() -> Generator[dict[str, AsyncMock | MagicMock]]:
    """Yield dictionary of mocked functions required for successful test_form execution."""
    with (
        patch(
            BASE_CONFIG_FLOW + "WebioAPI.check_connection",
            return_value=True,
        ) as check_connection,
        patch(
            BASE_CONFIG_FLOW + "WebioAPI.refresh_device_info",
            return_value=True,
        ) as refresh_device_info,
        patch(
            BASE_NASWEB_DATA + "NASwebData.get_webhook_url",
            return_value="http://127.0.0.1:8123/api/webhook/de705e77291402afa0dd961426e9f19bb53631a9f2a106c52cfd2d2266913c04",
        ) as get_webhook_url,
        patch(
            BASE_CONFIG_FLOW + "WebioAPI.get_serial_number",
            return_value=TEST_SERIAL_NUMBER,
        ) as get_serial,
        patch(
            BASE_CONFIG_FLOW + "WebioAPI.status_subscription",
            return_value=True,
        ) as status_subscription,
        patch(
            BASE_NASWEB_DATA + "NotificationCoordinator.check_connection",
            return_value=True,
        ) as check_status_confirmation,
    ):
        yield {
            BASE_CONFIG_FLOW + "WebioAPI.check_connection": check_connection,
            BASE_CONFIG_FLOW + "WebioAPI.refresh_device_info": refresh_device_info,
            BASE_NASWEB_DATA + "NASwebData.get_webhook_url": get_webhook_url,
            BASE_CONFIG_FLOW + "WebioAPI.get_serial_number": get_serial,
            BASE_CONFIG_FLOW + "WebioAPI.status_subscription": status_subscription,
            BASE_NASWEB_DATA
            + "NotificationCoordinator.check_connection": check_status_confirmation,
        }

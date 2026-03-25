"""Fixtures for the Tuya integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import (
    DEVICE_MOCKS,
    MockDeviceListener,
    create_device,
    create_listener,
    create_manager,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        title="Test Tuya entry",
        domain=DOMAIN,
        data={
            CONF_ENDPOINT: "test_endpoint",
            CONF_TERMINAL_ID: "test_terminal",
            CONF_TOKEN_INFO: "test_token",
            CONF_USER_CODE: "test_user_code",
        },
        unique_id="12345",
    )


@pytest.fixture
async def mock_loaded_entry(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> MockConfigEntry:
    """Mock a config entry."""
    # Setup
    mock_manager.device_map = {
        mock_device.id: mock_device,
    }
    mock_config_entry.add_to_hass(hass)

    # Initialize the component
    with (
        patch("homeassistant.components.tuya.Manager", return_value=mock_manager),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.tuya.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_tuya_login_control() -> Generator[MagicMock]:
    """Return a mocked Tuya login control."""
    with patch(
        "homeassistant.components.tuya.config_flow.LoginControl", autospec=True
    ) as login_control_mock:
        login_control = login_control_mock.return_value
        login_control.qr_code.return_value = {
            "success": True,
            "result": {
                "qrcode": "mocked_qr_code",
            },
        }
        login_control.login_result.return_value = (
            True,
            {
                "t": "mocked_t",
                "uid": "mocked_uid",
                "username": "mocked_username",
                "expire_time": "mocked_expire_time",
                "access_token": "mocked_access_token",
                "refresh_token": "mocked_refresh_token",
                "terminal_id": "mocked_terminal_id",
                "endpoint": "mocked_endpoint",
            },
        )
        yield login_control


@pytest.fixture
def mock_manager() -> Manager:
    """Fixture for Tuya Manager."""
    return create_manager()


@pytest.fixture
def mock_device_code() -> str:
    """Fixture to parametrize the type of the mock device.

    To set a configuration, tests can be marked with:
    @pytest.mark.parametrize("mock_device_code", ["device_code_1", "device_code_2"])
    """
    return None


@pytest.fixture
async def mock_devices(hass: HomeAssistant) -> list[CustomerDevice]:
    """Load all Tuya CustomerDevice fixtures.

    Use this to generate global snapshots for each platform.
    """
    return [await create_device(hass, device_code) for device_code in DEVICE_MOCKS]


@pytest.fixture
async def mock_device(hass: HomeAssistant, mock_device_code: str) -> CustomerDevice:
    """Load a single Tuya CustomerDevice fixture.

    Use this for testing behavior on a specific device.
    """
    return await create_device(hass, mock_device_code)


@pytest.fixture
def mock_listener(hass: HomeAssistant, mock_manager: Manager) -> MockDeviceListener:
    """Fixture for Tuya DeviceListener."""
    return create_listener(hass, mock_manager)

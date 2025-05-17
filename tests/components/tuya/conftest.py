"""Fixtures for the Tuya integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tuya_sharing.manager import Manager as _RealManager  # for type matching

from homeassistant.components.tuya.const import CONF_APP_TYPE, DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_old_config_entry() -> MockConfigEntry:
    """Mock an old config entry that can be migrated."""
    return MockConfigEntry(
        title="Old Tuya configuration entry",
        domain=DOMAIN,
        data={CONF_APP_TYPE: "tuyaSmart"},
        unique_id="12345",
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock an config entry."""
    data = {
        "user_code": "12345",
        "terminal_id": "mocked_terminal_id",
        "endpoint": "https://api.mock",
        "token_info": {
            "access_token": "mocked_access_token",
            "refresh_token": "mocked_refresh_token",
            "expire_time": 99999999,
            "t": 0,
            "uid": "mocked_uid",
        },
    }
    return MockConfigEntry(
        title="12345",
        domain=DOMAIN,
        data=data,
        unique_id="12345",
    )


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


@pytest.fixture(name="mock_tuya_manager")
def mock_tuya_manager_fixture() -> Generator[_RealManager]:
    """Mock out the Tuya ManagerCompat used in the tuya integration."""

    target = "homeassistant.components.tuya.ManagerCompat"
    with patch(target, autospec=True) as mock_manager_cls:
        mock_manager: _RealManager = mock_manager_cls.return_value

        # start tests with no devices
        mock_manager.device_map = {}

        # async methods the integration expects
        mock_manager.async_add_device = AsyncMock()
        mock_manager.async_remove_device = AsyncMock()
        mock_manager.async_update_devices = AsyncMock()
        mock_manager.async_send_commands = AsyncMock()

        yield mock_manager

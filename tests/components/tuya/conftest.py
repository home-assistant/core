"""Fixtures for the Tuya integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.tuya.const import CONF_APP_TYPE, CONF_USER_CODE, DOMAIN

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
    return MockConfigEntry(
        title="12345",
        domain=DOMAIN,
        data={CONF_USER_CODE: "12345"},
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


@pytest.fixture
def mock_tuya_device() -> Generator[MagicMock]:
    """Return a mocked Tuya device."""
    with patch("tuya_sharing.CustomerDevice", autospec=True) as device_mock:
        device = device_mock.return_value
        # Meaningless UUIDs
        device.id = "20b86c73-21d9-46de-81a4-9c06e4d9666b"
        device.name = "c6065fba-eef6-48cc-a00d-113fa673ff98"
        device.product_name = "f89c1e61-bf9e-46a0-aff0-7c749c405dfa"
        device.product_id = "bd9ee8fe-e0dd-42f8-b3ce-8c8fad984fda"
        yield device


@pytest.fixture
def mock_tuya_manager() -> Generator[MagicMock]:
    """Return a mocked Tuya manager."""
    with patch("tuya_sharing.Manager", autospec=True) as manager_mock:
        manager = manager_mock.return_value
        # Meaningless UUIDs
        manager.terminal_id = "7cd96aff-6ec8-4006-b093-3dbff7947591"
        yield manager

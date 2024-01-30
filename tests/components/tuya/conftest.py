"""Fixtures for the Tuya integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tuya.const import CONF_APP_TYPE, DOMAIN, TUYA_SMART_APP

from tests.common import MockConfigEntry


@pytest.fixture
def mock_old_config_entry() -> MockConfigEntry:
    """Mock an old config entry that can be migrated."""
    return MockConfigEntry(
        title="Old Tuya configuration entry",
        domain=DOMAIN,
        data={CONF_APP_TYPE: TUYA_SMART_APP},
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.tuya.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_tuya_login_control() -> Generator[MagicMock, None, None]:
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

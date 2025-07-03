"""Fixtures for the Tuya integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.components.tuya.const import (
    CONF_APP_TYPE,
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    DPCode,
    DPType,
)

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
def mock_manager() -> ManagerCompat:
    """Mock Tuya Manager."""
    manager = MagicMock(spec=ManagerCompat)
    manager.device_map = {}
    manager.mq = MagicMock()
    return manager


@pytest.fixture
def mock_device_arete_two_12l_dehumidifier_air_purifier() -> CustomerDevice:
    """Mock a Tuya Arete Two 12L Dehumidifier/Air Purifier device."""
    device = MagicMock(spec=CustomerDevice)
    device.id = "bf3fce6af592f12df3gbgq"
    device.name = "Dehumidifier"
    device.category = "cs"
    device.product_id = "zibqa9dutqyaxym2"
    device.product_name = "Arete\u00ae Two 12L Dehumidifier/Air Purifier"
    device.online = True
    device.function = {
        DPCode.SWITCH: MagicMock(type=DPType.BOOLEAN, value="{}"),
        DPCode.DEHUMIDITY_SET_VALUE: MagicMock(
            type=DPType.INTEGER,
            values='{"unit": "%", "min": 35, "max": 70, "scale": 0, "step": 5}',
        ),
        DPCode.CHILD_LOCK: MagicMock(type=DPType.BOOLEAN, value="{}"),
        DPCode.COUNTDOWN_SET: MagicMock(
            type=DPType.ENUM,
            values='{"range": ["cancel", "1h", "2h", "3h"]}',
        ),
    }
    device.status_range = {
        DPCode.SWITCH: MagicMock(type=DPType.BOOLEAN, value="{}"),
        DPCode.DEHUMIDITY_SET_VALUE: MagicMock(
            type=DPType.INTEGER,
            values='{"unit": "%", "min": 35, "max": 70, "scale": 0, "step": 5}',
        ),
        DPCode.CHILD_LOCK: MagicMock(type=DPType.BOOLEAN, value="{}"),
        DPCode.HUMIDITY_INDOOR: MagicMock(
            type=DPType.INTEGER,
            values='{"unit": "%", "min": 0, "max": 100, "scale": 0, "step": 1}',
        ),
        DPCode.COUNTDOWN_SET: MagicMock(
            type=DPType.ENUM,
            values='{"range": ["cancel", "1h", "2h", "3h"]}',
        ),
        DPCode.COUNTDOWN_LEFT: MagicMock(
            type=DPType.INTEGER,
            values='{"unit": "h", "min": 0, "max": 24, "scale": 0, "step": 1}',
        ),
    }
    device.status = {
        DPCode.SWITCH: True,
        DPCode.DEHUMIDITY_SET_VALUE: 50,
        DPCode.CHILD_LOCK: False,
        DPCode.HUMIDITY_INDOOR: 47,
        DPCode.COUNTDOWN_SET: "cancel",
        DPCode.COUNTDOWN_LEFT: 0,
        DPCode.FAULT: 0,
    }
    return device

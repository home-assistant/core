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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_dumps

from tests.common import MockConfigEntry, async_load_json_object_fixture


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
async def mock_loaded_entry(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
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
        patch("homeassistant.components.tuya.ManagerCompat", return_value=mock_manager),
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
def mock_manager() -> ManagerCompat:
    """Mock Tuya Manager."""
    manager = MagicMock(spec=ManagerCompat)
    manager.device_map = {}
    manager.mq = MagicMock()
    return manager


@pytest.fixture
def mock_device_code() -> str:
    """Fixture to parametrize the type of the mock device.

    To set a configuration, tests can be marked with:
    @pytest.mark.parametrize("mock_device_code", ["device_code_1", "device_code_2"])
    """
    return None


@pytest.fixture
async def mock_device(hass: HomeAssistant, mock_device_code: str) -> CustomerDevice:
    """Mock a Tuya CustomerDevice."""
    details = await async_load_json_object_fixture(
        hass, f"{mock_device_code}.json", DOMAIN
    )
    device = MagicMock(spec=CustomerDevice)
    device.id = details["id"]
    device.name = details["name"]
    device.category = details["category"]
    device.product_id = details["product_id"]
    device.product_name = details["product_name"]
    device.online = details["online"]
    device.function = {
        key: MagicMock(type=value["type"], values=json_dumps(value["value"]))
        for key, value in details["function"].items()
    }
    device.status_range = {
        key: MagicMock(type=value["type"], values=json_dumps(value["value"]))
        for key, value in details["status_range"].items()
    }
    device.status = details["status"]
    return device

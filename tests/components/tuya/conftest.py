"""Fixtures for the Tuya integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from tuya_sharing import (
    CustomerApi,
    CustomerDevice,
    DeviceFunction,
    DeviceStatusRange,
    Manager,
)

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
from homeassistant.util import dt as dt_util

from . import DEVICE_MOCKS, MockDeviceListener

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
    """Mock Tuya Manager."""
    manager = MagicMock(spec=Manager)
    manager.device_map = {}
    manager.mq = MagicMock()
    manager.mq.client = MagicMock()
    manager.mq.client.is_connected = MagicMock(return_value=True)
    manager.customer_api = MagicMock(spec=CustomerApi)
    # Meaningless URL / UUIDs
    manager.customer_api.endpoint = "https://apigw.tuyaeu.com"
    manager.terminal_id = "7cd96aff-6ec8-4006-b093-3dbff7947591"
    return manager


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
    return [await _create_device(hass, device_code) for device_code in DEVICE_MOCKS]


@pytest.fixture
async def mock_device(hass: HomeAssistant, mock_device_code: str) -> CustomerDevice:
    """Load a single Tuya CustomerDevice fixture.

    Use this for testing behavior on a specific device.
    """
    return await _create_device(hass, mock_device_code)


async def _create_device(hass: HomeAssistant, mock_device_code: str) -> CustomerDevice:
    """Mock a Tuya CustomerDevice."""
    details = await async_load_json_object_fixture(
        hass, f"{mock_device_code}.json", DOMAIN
    )
    device = MagicMock(spec=CustomerDevice)

    # Use reverse of the product_id for testing
    device.id = mock_device_code.replace("_", "")[::-1]

    device.name = details["name"]
    device.category = details["category"]
    device.product_id = details["product_id"]
    device.product_name = details["product_name"]
    device.online = details["online"]
    device.sub = details.get("sub")
    device.time_zone = details.get("time_zone")
    device.active_time = details.get("active_time")
    if device.active_time:
        device.active_time = int(dt_util.as_timestamp(device.active_time))
    device.create_time = details.get("create_time")
    if device.create_time:
        device.create_time = int(dt_util.as_timestamp(device.create_time))
    device.update_time = details.get("update_time")
    if device.update_time:
        device.update_time = int(dt_util.as_timestamp(device.update_time))
    device.support_local = details.get("support_local")
    device.mqtt_connected = details.get("mqtt_connected")

    device.function = {
        key: DeviceFunction(
            code=value.get("code"),
            type=value["type"],
            values=json_dumps(value["value"]),
        )
        for key, value in details["function"].items()
    }
    device.status_range = {
        key: DeviceStatusRange(
            code=value.get("code"),
            type=value["type"],
            values=json_dumps(value["value"]),
        )
        for key, value in details["status_range"].items()
    }
    device.status = details["status"]
    for key, value in device.status.items():
        if device.status_range[key].type == "Json":
            device.status[key] = json_dumps(value)
    return device


@pytest.fixture
def mock_listener(hass: HomeAssistant, mock_manager: Manager) -> MockDeviceListener:
    """Create a DeviceListener for testing."""
    listener = MockDeviceListener(hass, mock_manager)
    mock_manager.add_device_listener(listener)
    return listener

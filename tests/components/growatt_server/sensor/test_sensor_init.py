"""Tests for the Growatt server sensor integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.growatt_server.const import (
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    LOGIN_INVALID_AUTH_CODE,
    LOGIN_LOCKED_CODE,
)
from homeassistant.components.growatt_server.sensor import get_device_list
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryError


@pytest.fixture
def mock_api():
    """Fixture to mock the Growatt API."""
    return MagicMock()


def test_get_device_list_success(mock_api) -> None:
    """Test successful retrieval of device list."""
    mock_api.login.return_value = {"success": True, "user": {"id": "user123"}}
    mock_api.plant_list.return_value = {"data": [{"plantId": "plant123"}]}
    mock_api.device_list.return_value = [{"deviceType": "inverter", "deviceSn": "123"}]
    mock_api.is_plant_noah_system.return_value = {"result": 0}

    config = {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
        CONF_PLANT_ID: DEFAULT_PLANT_ID,
    }

    devices, plant_id = get_device_list(mock_api, config)

    assert plant_id == "plant123"
    assert len(devices) == 1
    assert devices[0]["deviceType"] == "inverter"


def test_get_device_list_invalid_auth(mock_api) -> None:
    """Test login failure with invalid authentication."""
    mock_api.login.return_value = {"success": False, "msg": LOGIN_INVALID_AUTH_CODE}

    config = {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
        CONF_PLANT_ID: DEFAULT_PLANT_ID,
    }

    with pytest.raises(
        ConfigEntryError, match="Username, Password or URL may be incorrect!"
    ):
        get_device_list(mock_api, config)


def test_get_device_list_account_locked(mock_api) -> None:
    """Test login failure with account locked."""
    mock_api.login.return_value = {
        "success": False,
        "msg": LOGIN_LOCKED_CODE,
        "error": "Account locked",
    }

    config = {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
        CONF_PLANT_ID: DEFAULT_PLANT_ID,
    }

    with pytest.raises(ConfigEntryError, match="Account locked"):
        get_device_list(mock_api, config)


def test_get_device_list_unknown_error(mock_api) -> None:
    """Test login failure with unknown error."""
    mock_api.login.return_value = {
        "success": False,
        "msg": "unknown_error",
        "error": "Unknown error occurred",
    }

    config = {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
        CONF_PLANT_ID: DEFAULT_PLANT_ID,
    }

    with pytest.raises(
        ConfigEntryError,
        match="Unknown auth error, server responds: Unknown error occurred",
    ):
        get_device_list(mock_api, config)


def test_get_device_list_noah_system(mock_api) -> None:
    """Test fetching devices for a plant with Noah system."""
    mock_api.login.return_value = {"success": True, "user": {"id": "user123"}}
    mock_api.plant_list.return_value = {"data": [{"plantId": "plant123"}]}
    mock_api.device_list.return_value = [{"deviceType": "inverter", "deviceSn": "123"}]
    mock_api.is_plant_noah_system.return_value = {
        "result": 1,
        "obj": {
            "isPlantNoahSystem": True,
            "deviceSn": "noah123",
            "alias": "Noah Device",
        },
    }
    mock_api.noah_system_status.return_value = {
        "obj": {"deviceType": "noah", "deviceSn": "noah123", "alias": "Noah Device"}
    }

    config = {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
        CONF_PLANT_ID: DEFAULT_PLANT_ID,
    }

    devices, plant_id = get_device_list(mock_api, config)

    assert plant_id == "plant123"
    assert len(devices) == 2
    assert devices[1]["deviceType"] == "noah"
    assert devices[1]["deviceSn"] == "noah123"

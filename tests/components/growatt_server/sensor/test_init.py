"""Tests for the Growatt server sensor integration initialization."""

from unittest.mock import patch

import pytest

from homeassistant.components.growatt_server.const import (
    DEFAULT_PLANT_ID,
    LOGIN_INVALID_AUTH_CODE,
    LOGIN_LOCKED_CODE,
)
from homeassistant.components.growatt_server.sensor import get_device_list
from homeassistant.exceptions import ConfigEntryError


@pytest.fixture
def mock_api():
    """Fixture to mock the Growatt API."""
    with patch("growattServer.GrowattApi") as mock_api:
        yield mock_api.return_value


def test_get_device_list_success(mock_api) -> None:
    """Test successful retrieval of device list."""
    mock_api.login.return_value = {"success": True, "user": {"id": "user123"}}
    mock_api.device_list.return_value = [{"deviceSn": "device1"}]
    mock_api.plant_list.return_value = {"data": [{"plantId": "plant123"}]}

    config = {
        "username": "test_user",
        "password": "test_pass",
        "plant_id": DEFAULT_PLANT_ID,
    }

    devices, plant_id = get_device_list(mock_api, config)

    assert plant_id == "plant123"
    assert devices == [{"deviceSn": "device1"}]
    mock_api.login.assert_called_once_with("test_user", "test_pass")
    mock_api.device_list.assert_called_once_with("plant123")


def test_get_device_list_invalid_auth(mock_api) -> None:
    """Test login failure due to invalid credentials."""
    mock_api.login.return_value = {"success": False, "msg": LOGIN_INVALID_AUTH_CODE}

    config = {
        "username": "test_user",
        "password": "wrong_pass",
        "plant_id": DEFAULT_PLANT_ID,
    }

    with pytest.raises(
        ConfigEntryError, match="Username, Password or URL may be incorrect!"
    ):
        get_device_list(mock_api, config)

    mock_api.login.assert_called_once_with("test_user", "wrong_pass")


def test_get_device_list_account_locked(mock_api) -> None:
    """Test login failure due to account lock."""
    mock_api.login.return_value = {
        "success": False,
        "msg": LOGIN_LOCKED_CODE,
        "error": "Account locked",
    }

    config = {
        "username": "test_user",
        "password": "test_pass",
        "plant_id": DEFAULT_PLANT_ID,
    }

    with pytest.raises(ConfigEntryError, match="Account locked"):
        get_device_list(mock_api, config)

    mock_api.login.assert_called_once_with("test_user", "test_pass")


def test_get_device_list_unknown_error(mock_api) -> None:
    """Test login failure due to an unknown error."""
    mock_api.login.return_value = {
        "success": False,
        "msg": "unknown_error",
        "error": "Unknown error occurred",
    }

    config = {
        "username": "test_user",
        "password": "test_pass",
        "plant_id": DEFAULT_PLANT_ID,
    }

    with pytest.raises(
        ConfigEntryError, match="Unknown error, server responds: Unknown error occurred"
    ):
        get_device_list(mock_api, config)

    mock_api.login.assert_called_once_with("test_user", "test_pass")


def test_get_device_list_no_plant_id(mock_api) -> None:
    """Test retrieval of device list when no plant ID is provided."""
    mock_api.login.return_value = {"success": True, "user": {"id": "user123"}}
    mock_api.plant_list.return_value = {"data": [{"plantId": "plant123"}]}
    mock_api.device_list.return_value = [{"deviceSn": "device1"}]

    config = {
        "username": "test_user",
        "password": "test_pass",
        "plant_id": DEFAULT_PLANT_ID,
    }

    devices, plant_id = get_device_list(mock_api, config)

    assert plant_id == "plant123"
    assert devices == [{"deviceSn": "device1"}]
    mock_api.login.assert_called_once_with("test_user", "test_pass")
    mock_api.plant_list.assert_called_once_with("user123")
    mock_api.device_list.assert_called_once_with("plant123")

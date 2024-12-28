"""Test the Api."""

import json
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.cosa.api import Api


@pytest.fixture
def api():
    """Fixture for initializing the Api."""
    return Api("test-username", "test-password")


def test_api_initialization(api) -> None:
    """Test the initialization of the Api."""
    assert api._Api__username == "test-username"
    assert api._Api__password == "test-password"
    assert api._Api__authToken is None


@patch("homeassistant.components.cosa.api.Api.getConnection")
def test_login_success(mock_get_connection, api) -> None:
    """Test successful login."""
    mock_conn = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.getresponse.return_value.read.return_value = json.dumps(
        {"authToken": "test-token", "ok": 1}
    )
    mock_conn.getresponse.return_value.status = 200

    assert api.login() is True
    assert api._Api__authToken == "test-token"


@patch("homeassistant.components.cosa.api.Api.getConnection")
def test_login_failure(mock_get_connection, api) -> None:
    """Test failed login."""
    mock_conn = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.getresponse.return_value.read.return_value = json.dumps({"ok": 0})
    mock_conn.getresponse.return_value.status = 200

    assert api.login() is False
    assert api._Api__authToken is None


@patch("homeassistant.components.cosa.api.Api.getConnection")
def test_get_endpoints_success(mock_get_connection, api) -> None:
    """Test successful retrieval of endpoints."""
    api._Api__authToken = "test-token"
    mock_conn = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.getresponse.return_value.read.return_value = json.dumps(
        {"endpoints": ["endpoint1", "endpoint2"], "ok": 1}
    )
    mock_conn.getresponse.return_value.status = 200

    endpoints = api.getEndpoints()
    assert endpoints == ["endpoint1", "endpoint2"]


@patch("homeassistant.components.cosa.api.Api.getConnection")
def test_get_endpoints_failure(mock_get_connection, api) -> None:
    """Test failed retrieval of endpoints."""
    api._Api__authToken = "test-token"
    mock_conn = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.getresponse.return_value.read.return_value = json.dumps({"ok": 0})
    mock_conn.getresponse.return_value.status = 200

    endpoints = api.getEndpoints()
    assert endpoints is None


@patch("homeassistant.components.cosa.api.Api.getConnection")
def test_set_target_temperatures_success(mock_get_connection, api) -> None:
    """Test successful setting of target temperatures."""
    api._Api__authToken = "test-token"
    mock_conn = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.getresponse.return_value.read.return_value = json.dumps({"ok": 1})
    mock_conn.getresponse.return_value.status = 200

    result = api.setTargetTemperatures("endpoint1", 20, 18, 16, 22)
    assert result is True


@patch("homeassistant.components.cosa.api.Api.getConnection")
def test_set_target_temperatures_failure(mock_get_connection, api) -> None:
    """Test failed setting of target temperatures."""
    api._Api__authToken = "test-token"
    mock_conn = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.getresponse.return_value.read.return_value = json.dumps({"ok": 0})
    mock_conn.getresponse.return_value.status = 200

    result = api.setTargetTemperatures("endpoint1", 20, 18, 16, 22)
    assert result is False

"""Tests for the Schluter DITRA-HEAT API client."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError, ClientResponseError
import pytest

from homeassistant.components.schluter.api import (
    CannotConnectError,
    InvalidCredentialsError,
    InvalidSessionError,
    SchluterApi,
    SchluterThermostat,
    _parse_thermostat,
    _to_celsius,
)

MOCK_THERMOSTAT_DATA = {
    "SerialNumber": "AA-BB-CC-11-22-33",
    "Room": "Bathroom",
    "Temperature": 2150,
    "SetPointTemp": 2400,
    "MinTemp": 500,
    "MaxTemp": 3500,
    "Heating": True,
    "Online": True,
    "LoadMeasuredWatt": 150,
    "SWVersion": "1.0.0",
}

MOCK_THERMOSTATS_RESPONSE = {"Groups": [{"Thermostats": [MOCK_THERMOSTAT_DATA]}]}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (2150, 21.5),
        (2400, 24.0),
        (500, 5.0),
        (3500, 35.0),
        (2175, 22.0),
    ],
    ids=["21.5", "24.0", "5.0", "35.0", "round_to_half"],
)
def test_to_celsius(raw: int, expected: float) -> None:
    """Test integer-to-Celsius conversion rounds to 0.5 steps."""
    assert _to_celsius(raw) == expected


def test_parse_thermostat() -> None:
    """Test that a raw API dict is correctly parsed into a SchluterThermostat."""
    result = _parse_thermostat(MOCK_THERMOSTAT_DATA)
    assert isinstance(result, SchluterThermostat)
    assert result.serial_number == "AA-BB-CC-11-22-33"
    assert result.name == "Bathroom"
    assert result.temperature == 21.5
    assert result.set_point_temp == 24.0
    assert result.min_temp == 5.0
    assert result.max_temp == 35.0
    assert result.is_heating is True
    assert result.is_online is True
    assert result.load_measured_watt == 150
    assert result.sw_version == "1.0.0"


def _make_api() -> SchluterApi:
    session = MagicMock()
    return SchluterApi(session)


def _mock_response(status: int = 200, json_data: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=json_data or {})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


def _http_error(status: int) -> ClientResponseError:
    """Build a ClientResponseError with a mock request_info so str() works."""
    request_info = MagicMock()
    request_info.real_url = "https://test.example.com"
    return ClientResponseError(request_info, (), status=status)


class TestAsyncGetSession:
    """Tests for SchluterApi.async_get_session."""

    async def test_success(self) -> None:
        """Test successful authentication returns a session ID."""
        api = _make_api()
        resp = _mock_response(json_data={"SessionId": "test-session", "ErrorCode": 0})
        api._websession.post.return_value = resp

        session_id = await api.async_get_session("user@example.com", "password")

        assert session_id == "test-session"

    async def test_invalid_credentials_error_code_1(self) -> None:
        """Test ErrorCode 1 raises InvalidCredentialsError."""
        api = _make_api()
        resp = _mock_response(json_data={"ErrorCode": 1})
        api._websession.post.return_value = resp

        with pytest.raises(InvalidCredentialsError):
            await api.async_get_session("user@example.com", "wrong")

    async def test_invalid_credentials_error_code_2(self) -> None:
        """Test ErrorCode 2 raises InvalidCredentialsError."""
        api = _make_api()
        resp = _mock_response(json_data={"ErrorCode": 2})
        api._websession.post.return_value = resp

        with pytest.raises(InvalidCredentialsError):
            await api.async_get_session("user@example.com", "wrong")

    async def test_network_error_raises_cannot_connect(self) -> None:
        """Test that a network error raises CannotConnectError."""
        api = _make_api()
        api._websession.post.side_effect = ClientError("network error")

        with pytest.raises(CannotConnectError):
            await api.async_get_session("user@example.com", "password")

    async def test_http_error_raises_cannot_connect(self) -> None:
        """Test that a non-auth HTTP error raises CannotConnectError."""
        api = _make_api()
        resp = _mock_response(status=500)
        resp.raise_for_status.side_effect = _http_error(500)
        api._websession.post.return_value = resp

        with pytest.raises(CannotConnectError):
            await api.async_get_session("user@example.com", "password")


class TestAsyncGetThermostats:
    """Tests for SchluterApi.async_get_thermostats."""

    async def test_success(self) -> None:
        """Test successful fetch returns parsed thermostats."""
        api = _make_api()
        resp = _mock_response(json_data=MOCK_THERMOSTATS_RESPONSE)
        api._websession.get.return_value = resp

        thermostats = await api.async_get_thermostats("session-id")

        assert len(thermostats) == 1
        assert thermostats[0].serial_number == "AA-BB-CC-11-22-33"

    async def test_401_raises_invalid_session(self) -> None:
        """Test HTTP 401 raises InvalidSessionError."""
        api = _make_api()
        resp = _mock_response(status=401)
        resp.raise_for_status.side_effect = _http_error(401)
        api._websession.get.return_value = resp

        with pytest.raises(InvalidSessionError):
            await api.async_get_thermostats("expired-session")

    async def test_empty_groups_raises_invalid_session(self) -> None:
        """Test empty Groups in response raises InvalidSessionError."""
        api = _make_api()
        resp = _mock_response(json_data={"Groups": []})
        api._websession.get.return_value = resp

        with pytest.raises(InvalidSessionError):
            await api.async_get_thermostats("session-id")

    async def test_missing_groups_raises_invalid_session(self) -> None:
        """Test missing Groups key in response raises InvalidSessionError."""
        api = _make_api()
        resp = _mock_response(json_data={})
        api._websession.get.return_value = resp

        with pytest.raises(InvalidSessionError):
            await api.async_get_thermostats("session-id")

    async def test_network_error_raises_cannot_connect(self) -> None:
        """Test that a network error raises CannotConnectError."""
        api = _make_api()
        api._websession.get.side_effect = ClientError("network error")

        with pytest.raises(CannotConnectError):
            await api.async_get_thermostats("session-id")

    async def test_http_error_raises_cannot_connect(self) -> None:
        """Test that a non-auth HTTP error raises CannotConnectError."""
        api = _make_api()
        resp = _mock_response(status=500)
        resp.raise_for_status.side_effect = _http_error(500)
        api._websession.get.return_value = resp

        with pytest.raises(CannotConnectError):
            await api.async_get_thermostats("session-id")


class TestAsyncSetTemperature:
    """Tests for SchluterApi.async_set_temperature."""

    async def test_success(self) -> None:
        """Test successful temperature set."""
        api = _make_api()
        resp = _mock_response(json_data={"Success": True})
        api._websession.post.return_value = resp

        await api.async_set_temperature("session-id", "AA-BB-CC", 22.5)

    async def test_api_failure_raises_cannot_connect(self) -> None:
        """Test Success=false in response raises CannotConnectError."""
        api = _make_api()
        resp = _mock_response(json_data={"Success": False})
        api._websession.post.return_value = resp

        with pytest.raises(CannotConnectError):
            await api.async_set_temperature("session-id", "AA-BB-CC", 22.5)

    async def test_401_raises_invalid_session(self) -> None:
        """Test HTTP 401 raises InvalidSessionError."""
        api = _make_api()
        resp = _mock_response(status=401)
        resp.raise_for_status.side_effect = _http_error(401)
        api._websession.post.return_value = resp

        with pytest.raises(InvalidSessionError):
            await api.async_set_temperature("session-id", "AA-BB-CC", 22.5)

    async def test_network_error_raises_cannot_connect(self) -> None:
        """Test that a network error raises CannotConnectError."""
        api = _make_api()
        api._websession.post.side_effect = ClientError("network error")

        with pytest.raises(CannotConnectError):
            await api.async_set_temperature("session-id", "AA-BB-CC", 22.5)

    async def test_http_error_raises_cannot_connect(self) -> None:
        """Test that a non-auth HTTP error raises CannotConnectError."""
        api = _make_api()
        resp = _mock_response(status=500)
        resp.raise_for_status.side_effect = _http_error(500)
        api._websession.post.return_value = resp

        with pytest.raises(CannotConnectError):
            await api.async_set_temperature("session-id", "AA-BB-CC", 22.5)

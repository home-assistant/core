"""Tests for the Telldus Live API client."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from homeassistant.components.tellduslive.api import (
    LocalAPISession,
    Session,
    supports_local_api,
)
from homeassistant.components.tellduslive.const import (
    BATTERY_OK,
    DIM,
    DOWN,
    TURNOFF,
    TURNON,
    UP,
)

CLOUD_URL = "https://pa-api.telldus.com/json/"
LOCAL_URL = "http://192.0.2.1/api/"

DEVICES = {
    "device": [
        {"id": "1", "name": "Lamp", "state": TURNOFF, "methods": DIM | TURNON},
        {"id": "2", "name": "", "state": TURNON, "methods": TURNON},
    ]
}
SENSORS = {
    "sensor": [
        {
            "id": "1",
            "name": "Outdoor",
            "battery": BATTERY_OK,
            "data": [
                {"name": "temp", "scale": "0", "value": "21.5"},
                {"name": "humidity", "scale": "0", "value": "40"},
            ],
        },
        {"id": "3", "name": "No data"},
    ]
}


@pytest.fixture
def cloud_session() -> Session:
    """Return a cloud session."""
    return Session("public", "private", "token", "secret", application="HA")


@pytest.fixture
def mock_api() -> requests_mock.Mocker:
    """Mock the HTTP layer."""
    with requests_mock.Mocker() as mocker:
        yield mocker


def _mock_lists(mocker: requests_mock.Mocker) -> None:
    mocker.get(f"{CLOUD_URL}devices/list", json=DEVICES)
    mocker.get(f"{CLOUD_URL}sensors/list", json=SENSORS)


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"public_key": "public"}, {"private_key": "private"}, {"token": "token"}],
)
def test_session_missing_configuration(kwargs: dict[str, str]) -> None:
    """Test missing configuration raises."""
    with pytest.raises(ValueError, match="Missing configuration"):
        Session(**kwargs)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("TellstickZnet", True), ("TellstickNetV2", True), ("TellstickDuo", False)],
)
def test_supports_local_api(name: str, expected: bool) -> None:
    """Test local API support detection."""
    assert supports_local_api(name) is expected


def test_update_merges_devices_and_sensors(
    mock_api: requests_mock.Mocker, cloud_session: Session
) -> None:
    """Test unnamed devices and data-less sensors are skipped, sensors prefixed."""
    _mock_lists(mock_api)

    assert cloud_session.update() is True

    assert sorted(cloud_session.device_ids) == ["1", "_1"]
    assert cloud_session.device("1").is_sensor is False
    assert cloud_session.device("_1").is_sensor is True


@pytest.mark.parametrize("failing", ["devices/list", "sensors/list"])
def test_update_failed_request(
    mock_api: requests_mock.Mocker, cloud_session: Session, failing: str
) -> None:
    """Test update reports failure when one request fails."""
    _mock_lists(mock_api)
    mock_api.get(f"{CLOUD_URL}{failing}", status_code=500)

    assert cloud_session.update() is False


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"json": {"status": "success"}}, True),
        ({"json": {"status": "failed"}}, False),
        ({"json": {"error": "boom"}}, False),
        ({"status_code": 500}, False),
        ({"text": "not json"}, False),
    ],
)
def test_execute(
    mock_api: requests_mock.Mocker,
    cloud_session: Session,
    response: dict,
    expected: bool,
) -> None:
    """Test execute result handling."""
    mock_api.get(f"{CLOUD_URL}device/turnOn", **response)

    assert cloud_session.execute("device/turnOn", id="1") is expected


def test_device_commands_update_state(
    mock_api: requests_mock.Mocker, cloud_session: Session
) -> None:
    """Test commands update the local device state."""
    _mock_lists(mock_api)
    for method in ("turnOn", "turnOff", "dim", "up", "down"):
        mock_api.get(f"{CLOUD_URL}device/{method}", json={"status": "success"})
    cloud_session.update()
    device = cloud_session.device("1")

    assert device.turn_on() is True
    assert device.is_on is True
    assert device.dim(level=128) is True
    assert device.dim_level == 128
    assert device.is_on is True
    assert device.turn_off() is True
    assert device.is_on is False
    assert device.up() is True
    assert device.state == UP
    assert device.down() is True
    assert device.is_down is True
    assert device.state == DOWN
    assert mock_api.request_history[-1].qs == {"id": ["1"]}


def test_device_command_failure_keeps_state(
    mock_api: requests_mock.Mocker, cloud_session: Session
) -> None:
    """Test a failed command leaves the state untouched."""
    _mock_lists(mock_api)
    mock_api.get(f"{CLOUD_URL}device/turnOn", status_code=500)
    cloud_session.update()
    device = cloud_session.device("1")

    assert device.turn_on() is False
    assert device.state == TURNOFF


@pytest.mark.parametrize(
    ("statevalue", "expected"),
    [("100", 100), ("unde", 0), (None, 0), ("abc", None)],
)
def test_dim_level(
    mock_api: requests_mock.Mocker,
    cloud_session: Session,
    statevalue: str | None,
    expected: int | None,
) -> None:
    """Test dim level parsing."""
    mock_api.get(
        f"{CLOUD_URL}devices/list",
        json={"device": [{"id": "1", "name": "Lamp", "statevalue": statevalue}]},
    )
    mock_api.get(f"{CLOUD_URL}sensors/list", json={"sensor": []})
    cloud_session.update()

    assert cloud_session.device("1").dim_level == expected


def test_sensor_items(mock_api: requests_mock.Mocker, cloud_session: Session) -> None:
    """Test sensor item lookup by name and scale."""
    _mock_lists(mock_api)
    cloud_session.update()
    sensor = cloud_session.device("_1")

    assert [item.name for item in sensor.items] == ["temp", "humidity"]
    assert sensor.value("temp", 0) == "21.5"
    assert sensor.value("humidity", "0") == "40"
    assert sensor.item("temp", 1) is None


def test_device_info(mock_api: requests_mock.Mocker, cloud_session: Session) -> None:
    """Test info requests add the hub id."""
    _mock_lists(mock_api)
    mock_api.get(f"{CLOUD_URL}device/info", json={"id": "1", "model": "x"})
    cloud_session.update()

    assert cloud_session.device("1").info() == {
        "id": "1",
        "model": "x",
        "client": None,
    }
    assert cloud_session.device("_1").info()["client"] is None


def test_get_clients(mock_api: requests_mock.Mocker, cloud_session: Session) -> None:
    """Test cloud client listing."""
    mock_api.get(f"{CLOUD_URL}clients/list", json={"client": [{"id": "hub"}]})

    assert cloud_session.get_clients() == [{"id": "hub"}]


def test_get_clients_failure(
    mock_api: requests_mock.Mocker, cloud_session: Session
) -> None:
    """Test cloud client listing failure."""
    mock_api.get(f"{CLOUD_URL}clients/list", status_code=500)

    assert cloud_session.get_clients() == []


def test_cloud_authorize_url_failure(cloud_session: Session) -> None:
    """Test no authorize URL is returned when the request fails."""
    with patch.object(
        cloud_session._session, "fetch_request_token", side_effect=OSError("down")
    ):
        assert cloud_session.authorize_url is None


def test_cloud_authorize(cloud_session: Session) -> None:
    """Test cloud authorization stores the tokens."""
    with patch.object(
        cloud_session._session,
        "_fetch_token",
        return_value={"oauth_token": "tok", "oauth_token_secret": "sec"},
    ):
        assert cloud_session.authorize() is True

    assert cloud_session.access_token == "tok"
    assert cloud_session.access_token_secret == "sec"


def test_cloud_authorize_failure(cloud_session: Session) -> None:
    """Test cloud authorization failure."""
    with patch.object(
        cloud_session._session, "_fetch_token", side_effect=ValueError("bad")
    ):
        assert cloud_session.authorize() is None


def test_local_session_refreshes_token_on_init(mock_api: requests_mock.Mocker) -> None:
    """Test a stored token is refreshed and used as bearer."""
    mock_api.get(
        f"{LOCAL_URL}refreshToken", json={"token": "new", "expires": 1900000000}
    )

    session = Session(host="192.0.2.1", token="old")

    assert session.access_token == "new"
    assert session.is_authorized is True
    assert session._session.headers["Authorization"] == "Bearer old"


def test_local_authorize_flow(mock_api: requests_mock.Mocker) -> None:
    """Test the local token request and authorization."""
    mock_api.put(f"{LOCAL_URL}token", json={"token": "req", "authUrl": "http://auth"})
    mock_api.get(f"{LOCAL_URL}token", json={"token": "acc", "expires": 1900000000})
    session = Session(host="192.0.2.1", application="HA")

    assert session.authorize_url == "http://auth"
    assert mock_api.request_history[-1].text == "app=HA"
    assert session.is_authorized is False
    assert session.authorize() is True
    assert session.access_token == "acc"
    assert session.access_token_secret is None
    assert mock_api.request_history[-1].qs == {"token": ["req"]}


def test_local_authorize_url_failure(mock_api: requests_mock.Mocker) -> None:
    """Test local authorize URL failure."""
    mock_api.put(f"{LOCAL_URL}token", status_code=500)

    assert Session(host="192.0.2.1").authorize_url is None


@pytest.mark.parametrize(
    ("age", "refreshes"),
    [(timedelta(hours=13), 1), (timedelta(hours=1), 0)],
)
def test_local_maybe_refresh_token(
    mock_api: requests_mock.Mocker, age: timedelta, refreshes: int
) -> None:
    """Test the token is only refreshed after 12 hours."""
    mock_api.get(
        f"{LOCAL_URL}refreshToken", json={"token": "new", "expires": 1900000000}
    )
    session = LocalAPISession("192.0.2.1", "HA")
    session.token_timestamp = datetime.now() - age

    session.maybe_refresh_token()

    assert mock_api.call_count == refreshes


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (
            b"TellstickZnet:aa:bb:cc",
            [
                {
                    "name": "192.0.2.1",
                    "type": "TellstickZnet",
                    "id": "aa",
                    "version": "cc",
                }
            ],
        ),
        (b"too:short", []),
    ],
)
def test_local_discovery(reply: bytes, expected: list[dict[str, str]]) -> None:
    """Test discovery socket parsing."""
    session = Session(host="192.0.2.1")
    with patch("homeassistant.components.tellduslive.api.socket.socket") as sock_cls:
        sock: MagicMock = sock_cls.return_value
        sock.recvfrom.return_value = (reply, ("192.0.2.1", 30303))

        assert session.get_clients() == expected


def test_local_discovery_timeout() -> None:
    """Test discovery timeout returns no hubs."""
    session = Session(host="192.0.2.1")
    with patch("homeassistant.components.tellduslive.api.socket.socket") as sock_cls:
        sock_cls.return_value.recvfrom.side_effect = TimeoutError

        assert session.get_clients() == []

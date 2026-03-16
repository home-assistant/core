"""Tests for the Tomato device tracker platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.tomato.device_tracker import (
    CONF_HTTP_ID,
    PLATFORM_SCHEMA,
    TomatoData,
    TomatoDeviceEntity,
    async_setup_platform,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

GOOD_RESPONSE_TEXT = (
    "wldev = [ ['eth1','F4:F5:D8:AA:AA:AA',"
    "-42,5500,1000,7043,0],['eth1','58:EF:68:00:00:00',"
    "-42,5500,1000,7043,0]];\n"
    "dhcpd_lease = [ ['chromecast','172.10.10.5','F4:F5:D8:AA:AA:AA',"
    "'0 days, 16:17:08'],['wemo','172.10.10.6','58:EF:68:00:00:00',"
    "'0 days, 12:09:08']];"
)

PARTIAL_RESPONSE_TEXT = (
    "wldev = [ ['eth1','F4:F5:D8:AA:AA:AA',-42,5500,1000,7043,0]];\n"
    "dhcpd_lease = [ ['chromecast','172.10.10.5','F4:F5:D8:AA:AA:AA',"
    "'0 days, 16:17:08'],['wemo','172.10.10.6','58:EF:68:00:00:00',"
    "'0 days, 12:09:08']];"
)


def _make_config(**overrides: object) -> dict:
    """Create a test config."""
    config: dict = {
        CONF_HOST: "tomato-router",
        CONF_USERNAME: "foo",
        CONF_PASSWORD: "bar",
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_HTTP_ID: "1234567890",
    }
    config.update(overrides)
    return config


def _mock_response(text: str | None, status_code: int) -> MagicMock:
    """Create a mock response."""
    response = MagicMock()
    response.text = text
    response.status_code = status_code
    return response


# --- Schema validation tests ---


def test_config_missing_host() -> None:
    """Test config validation with missing host."""
    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: DEVICE_TRACKER_DOMAIN,
                CONF_USERNAME: "bar",
                CONF_PASSWORD: "foo",
                CONF_HTTP_ID: "0987654321",
            }
        )


def test_config_missing_username() -> None:
    """Test config validation with missing username."""
    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: DEVICE_TRACKER_DOMAIN,
                CONF_HOST: "tomato-router",
                CONF_PASSWORD: "foo",
                CONF_HTTP_ID: "0987654321",
            }
        )


def test_config_missing_password() -> None:
    """Test config validation with missing password."""
    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: DEVICE_TRACKER_DOMAIN,
                CONF_HOST: "tomato-router",
                CONF_USERNAME: "bar",
                CONF_HTTP_ID: "0987654321",
            }
        )


def test_config_missing_http_id() -> None:
    """Test config validation with missing http_id."""
    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: DEVICE_TRACKER_DOMAIN,
                CONF_HOST: "tomato-router",
                CONF_USERNAME: "bar",
                CONF_PASSWORD: "foo",
            }
        )


def test_config_bad_port() -> None:
    """Test config validation with bad port."""
    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: DEVICE_TRACKER_DOMAIN,
                CONF_HOST: "tomato-router",
                CONF_PORT: -123456789,
                CONF_USERNAME: "bar",
                CONF_PASSWORD: "foo",
                CONF_HTTP_ID: "0987654321",
            }
        )


# --- TomatoData tests ---


def test_tomato_data_default_http_port() -> None:
    """Test default HTTP port is 80."""
    data = TomatoData(_make_config())
    assert data._req.url == "http://tomato-router:80/update.cgi"


def test_tomato_data_default_https_port() -> None:
    """Test default HTTPS port is 443."""
    data = TomatoData(_make_config(**{CONF_SSL: True}))
    assert data._req.url == "https://tomato-router:443/update.cgi"


def test_tomato_data_custom_port() -> None:
    """Test custom port configuration."""
    data = TomatoData(_make_config(**{CONF_PORT: 1234}))
    assert data._req.url == "http://tomato-router:1234/update.cgi"


def test_tomato_data_auth_headers() -> None:
    """Test authentication headers are set correctly."""
    data = TomatoData(_make_config())
    assert data._req.headers["Authorization"] == "Basic Zm9vOmJhcg=="


def test_tomato_data_request_body() -> None:
    """Test request body contains expected data."""
    data = TomatoData(_make_config())
    assert "_http_id=1234567890" in data._req.body
    assert "exec=devlist" in data._req.body


@patch("requests.Session.send")
def test_tomato_data_update_success(mock_send: MagicMock) -> None:
    """Test successful data update."""
    mock_send.return_value = _mock_response(GOOD_RESPONSE_TEXT, 200)

    data = TomatoData(_make_config())
    result = data.update()

    assert result is True
    assert data.connected_macs == {"F4:F5:D8:AA:AA:AA", "58:EF:68:00:00:00"}
    assert "F4:F5:D8:AA:AA:AA" in data.devices
    assert data.devices["F4:F5:D8:AA:AA:AA"] == {
        "hostname": "chromecast",
        "ip": "172.10.10.5",
    }
    assert data.devices["58:EF:68:00:00:00"] == {
        "hostname": "wemo",
        "ip": "172.10.10.6",
    }


@patch("requests.Session.send")
def test_tomato_data_ssl_verify(mock_send: MagicMock) -> None:
    """Test SSL verify parameter is passed correctly."""
    mock_send.return_value = _mock_response(GOOD_RESPONSE_TEXT, 200)

    data = TomatoData(_make_config(**{CONF_SSL: True, CONF_VERIFY_SSL: False}))
    data.update()

    mock_send.assert_called_once_with(data._req, timeout=60, verify=False)


@patch("requests.Session.send")
def test_tomato_data_no_ssl_no_verify(mock_send: MagicMock) -> None:
    """Test no SSL does not pass verify parameter."""
    mock_send.return_value = _mock_response(GOOD_RESPONSE_TEXT, 200)

    data = TomatoData(_make_config())
    data.update()

    mock_send.assert_called_once_with(data._req, timeout=60)


@patch("requests.Session.send")
def test_tomato_data_auth_failure(mock_send: MagicMock) -> None:
    """Test authentication failure."""
    mock_send.return_value = _mock_response(None, 401)

    data = TomatoData(_make_config())
    result = data.update()

    assert result is False


@patch("requests.Session.send", side_effect=requests.exceptions.ConnectionError)
def test_tomato_data_connection_error(mock_send: MagicMock) -> None:
    """Test connection error handling."""
    data = TomatoData(_make_config())
    result = data.update()

    assert result is False


@patch("requests.Session.send", side_effect=requests.exceptions.Timeout)
def test_tomato_data_timeout(mock_send: MagicMock) -> None:
    """Test timeout handling."""
    data = TomatoData(_make_config())
    result = data.update()

    assert result is False


@patch("requests.Session.send")
def test_tomato_data_parse_error(mock_send: MagicMock) -> None:
    """Test JSON parse error handling."""
    mock_send.return_value = _mock_response("wldev = bad json data;", 200)

    data = TomatoData(_make_config())
    result = data.update()

    assert result is False


# --- async_setup_platform tests ---


async def test_setup_platform_success(hass: HomeAssistant) -> None:
    """Test successful platform setup creates entities."""
    entities: list[TomatoDeviceEntity] = []

    def mock_add_entities(
        new_entities: list[TomatoDeviceEntity],
        update_before_add: bool = False,
    ) -> None:
        entities.extend(new_entities)

    config = _make_config()

    with patch("requests.Session.send") as mock_send:
        mock_send.return_value = _mock_response(GOOD_RESPONSE_TEXT, 200)
        await async_setup_platform(hass, config, mock_add_entities)

    assert len(entities) == 2

    macs = {e.mac_address for e in entities}
    assert macs == {"F4:F5:D8:AA:AA:AA", "58:EF:68:00:00:00"}

    chromecast = next(e for e in entities if e.mac_address == "F4:F5:D8:AA:AA:AA")
    assert chromecast.hostname == "chromecast"
    assert chromecast.ip_address == "172.10.10.5"
    assert chromecast.is_connected is True
    assert chromecast.name == "chromecast"

    wemo = next(e for e in entities if e.mac_address == "58:EF:68:00:00:00")
    assert wemo.hostname == "wemo"
    assert wemo.ip_address == "172.10.10.6"
    assert wemo.is_connected is True
    assert wemo.name == "wemo"


async def test_setup_platform_failure_raises_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test platform setup raises PlatformNotReady on failure."""
    entities: list[TomatoDeviceEntity] = []

    def mock_add_entities(
        new_entities: list[TomatoDeviceEntity],
        update_before_add: bool = False,
    ) -> None:
        entities.extend(new_entities)

    config = _make_config()

    with (
        patch(
            "requests.Session.send",
            side_effect=requests.exceptions.ConnectionError,
        ),
        pytest.raises(PlatformNotReady),
    ):
        await async_setup_platform(hass, config, mock_add_entities)

    assert len(entities) == 0


async def test_entity_disconnected(hass: HomeAssistant) -> None:
    """Test entity shows disconnected when not in wldev."""
    entities: list[TomatoDeviceEntity] = []

    def mock_add_entities(
        new_entities: list[TomatoDeviceEntity],
        update_before_add: bool = False,
    ) -> None:
        entities.extend(new_entities)

    config = _make_config()

    with patch("requests.Session.send") as mock_send:
        mock_send.return_value = _mock_response(PARTIAL_RESPONSE_TEXT, 200)
        await async_setup_platform(hass, config, mock_add_entities)

    assert len(entities) == 2

    chromecast = next(e for e in entities if e.mac_address == "F4:F5:D8:AA:AA:AA")
    assert chromecast.is_connected is True

    wemo = next(e for e in entities if e.mac_address == "58:EF:68:00:00:00")
    assert wemo.is_connected is False


async def test_entity_name_fallback_to_mac(hass: HomeAssistant) -> None:
    """Test entity name falls back to MAC when hostname is empty."""
    response_text = (
        "wldev = [ ['eth1','AA:BB:CC:DD:EE:FF',-42,5500,1000,7043,0]];\n"
        "dhcpd_lease = [ ['','172.10.10.7','AA:BB:CC:DD:EE:FF',"
        "'0 days, 16:17:08']];"
    )

    entities: list[TomatoDeviceEntity] = []

    def mock_add_entities(
        new_entities: list[TomatoDeviceEntity],
        update_before_add: bool = False,
    ) -> None:
        entities.extend(new_entities)

    config = _make_config()

    with patch("requests.Session.send") as mock_send:
        mock_send.return_value = _mock_response(response_text, 200)
        await async_setup_platform(hass, config, mock_add_entities)

    assert len(entities) == 1
    assert entities[0].name == "AA:BB:CC:DD:EE:FF"
    assert entities[0].hostname is None
    assert entities[0].ip_address == "172.10.10.7"

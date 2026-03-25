"""Tests for the Abode module."""

from http import HTTPStatus
from unittest.mock import Mock, patch

from jaraco.abode.exceptions import (
    AuthenticationException as AbodeAuthenticationException,
    Exception as AbodeException,
)
import pytest
from requests.exceptions import HTTPError

from homeassistant.components.abode import (
    AbodeSystem,
    _install_runtime_auth_guard,
    _is_auth_error,
    _is_auth_like_response,
    _start_reauth,
)
from homeassistant.components.abode.const import DOMAIN
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_change_settings(hass: HomeAssistant) -> None:
    """Test change_setting service."""
    await setup_platform(hass, ALARM_DOMAIN)

    with patch("jaraco.abode.client.Client.set_setting") as mock_set_setting:
        await hass.services.async_call(
            DOMAIN,
            "change_setting",
            {"setting": "confirm_snd", "value": "loud"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_setting.assert_called_once()


async def test_add_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id is set to Abode username."""
    mock_entry = await setup_platform(hass, ALARM_DOMAIN)
    # Set unique_id to None to match previous config entries
    hass.config_entries.async_update_entry(entry=mock_entry, unique_id=None)
    await hass.async_block_till_done()

    assert mock_entry.unique_id is None

    await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.unique_id == mock_entry.data[CONF_USERNAME]


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the Abode entry."""
    mock_entry = await setup_platform(hass, ALARM_DOMAIN)

    with (
        patch("jaraco.abode.client.Client.logout") as mock_logout,
        patch("jaraco.abode.event_controller.EventController.stop") as mock_events_stop,
    ):
        assert await hass.config_entries.async_unload(mock_entry.entry_id)
    mock_logout.assert_called_once()
    mock_events_stop.assert_called_once()


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test Abode credentials changing."""
    with patch(
        "homeassistant.components.abode.Abode",
        side_effect=AbodeAuthenticationException(
            (HTTPStatus.BAD_REQUEST, "auth error")
        ),
    ):
        config_entry = await setup_platform(hass, ALARM_DOMAIN)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    hass.config_entries.flow.async_abort(flows[0]["flow_id"])
    assert not hass.config_entries.flow.async_progress()


async def test_raise_config_entry_not_ready_when_offline(hass: HomeAssistant) -> None:
    """Config entry state is SETUP_RETRY when abode is offline."""
    with patch(
        "homeassistant.components.abode.Abode",
        side_effect=AbodeException("any"),
    ):
        config_entry = await setup_platform(hass, ALARM_DOMAIN)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    assert hass.config_entries.flow.async_progress() == []


def test_start_reauth_stops_event_stream_and_starts_flow() -> None:
    """Test runtime reauth starts flow and stops event stream for websocket mode."""
    abode_client = Mock()
    hass = Mock()
    hass.loop = Mock()
    entry = Mock()

    _start_reauth(hass, entry, abode_client, False, Exception("auth failed"))

    abode_client.events.stop.assert_called_once()
    hass.loop.call_soon_threadsafe.assert_called_once_with(
        entry.async_start_reauth, hass
    )
    entry.async_start_reauth.assert_not_called()


def test_start_reauth_polling_does_not_stop_event_stream() -> None:
    """Test runtime reauth does not stop event stream in polling mode."""
    abode_client = Mock()
    hass = Mock()
    hass.loop = Mock()
    entry = Mock()

    _start_reauth(hass, entry, abode_client, True, Exception("auth failed"))

    abode_client.events.stop.assert_not_called()
    hass.loop.call_soon_threadsafe.assert_called_once_with(
        entry.async_start_reauth, hass
    )
    entry.async_start_reauth.assert_not_called()


def test_start_reauth_handles_event_stop_error() -> None:
    """Test runtime reauth continues when stopping event stream fails."""
    abode_client = Mock()
    abode_client.events.stop.side_effect = RuntimeError("stop failed")
    hass = Mock()
    hass.loop = Mock()
    entry = Mock()

    _start_reauth(hass, entry, abode_client, False, Exception("auth failed"))

    hass.loop.call_soon_threadsafe.assert_called_once_with(
        entry.async_start_reauth, hass
    )
    entry.async_start_reauth.assert_not_called()


@pytest.mark.parametrize(
    ("error", "is_auth"),
    [
        (AbodeAuthenticationException((HTTPStatus.BAD_REQUEST, "auth")), True),
        (HTTPError(response=Mock(status_code=HTTPStatus.UNAUTHORIZED)), True),
        (HTTPError(response=Mock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)), False),
        (
            AbodeException(
                (HTTPStatus.INTERNAL_SERVER_ERROR, "Username and password do not match")
            ),
            True,
        ),
        (AbodeException((None, "Unauthorized token")), True),
        (AbodeException((None, None)), False),
        (AbodeException("any"), False),
        (AbodeException((HTTPStatus.FORBIDDEN, "forbidden")), True),
        (AbodeException((HTTPStatus.INTERNAL_SERVER_ERROR, "server error")), False),
        (RuntimeError("boom"), False),
    ],
)
def test_is_auth_error(error: Exception, is_auth: bool) -> None:
    """Test auth error detection from exceptions."""
    assert _is_auth_error(error) is is_auth


def test_is_auth_like_response() -> None:
    """Test auth-like response payload detection."""
    unauthorized = Mock(status_code=HTTPStatus.UNAUTHORIZED)
    assert _is_auth_like_response(unauthorized) is True

    server_error = Mock(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    assert _is_auth_like_response(server_error) is False

    invalid_json = Mock(status_code=HTTPStatus.OK)
    invalid_json.headers = {"Content-Type": "application/json"}
    invalid_json.json.side_effect = ValueError
    assert _is_auth_like_response(invalid_json) is False

    list_payload = Mock(status_code=HTTPStatus.OK)
    list_payload.headers = {"Content-Type": "application/json"}
    list_payload.json.return_value = ["not", "dict"]
    assert _is_auth_like_response(list_payload) is False

    error_code_payload = Mock(status_code=HTTPStatus.OK)
    error_code_payload.headers = {"Content-Type": "application/json"}
    error_code_payload.json.return_value = {"errorCode": 11002}
    assert _is_auth_like_response(error_code_payload) is True

    message_payload = Mock(status_code=HTTPStatus.OK)
    message_payload.headers = {"Content-Type": "application/json"}
    message_payload.json.return_value = {"message": "Unauthorized token"}
    assert _is_auth_like_response(message_payload) is True

    ok_payload = Mock(status_code=HTTPStatus.OK)
    ok_payload.headers = {"Content-Type": "application/json"}
    ok_payload.json.return_value = {"message": "ok"}
    assert _is_auth_like_response(ok_payload) is False

    text_payload = Mock(status_code=HTTPStatus.OK)
    text_payload.headers = {"Content-Type": "text/plain"}
    assert _is_auth_like_response(text_payload) is False


def test_runtime_auth_guard_for_exception_and_payload() -> None:
    """Test send_request wrapper triggers reauth for auth exception and payload."""
    # Exception path.
    abode_client = Mock()
    abode_client.send_request.side_effect = AbodeAuthenticationException(
        (HTTPStatus.UNAUTHORIZED, "unauthorized")
    )
    abode_system = AbodeSystem(abode_client, False)
    hass = Mock()
    entry = Mock()
    with patch("homeassistant.components.abode._start_reauth") as mock_start_reauth:
        _install_runtime_auth_guard(abode_system, hass, entry)

        with pytest.raises(AbodeAuthenticationException):
            abode_system.abode.send_request("GET", "/api/v1/panel")
        mock_start_reauth.assert_called_once()

    # Payload path.
    payload_response = Mock(status_code=HTTPStatus.OK)
    payload_response.headers = {"Content-Type": "application/json"}
    payload_response.json.return_value = {"errorCode": 13027}
    abode_client = Mock()
    abode_client.send_request.return_value = payload_response
    abode_system = AbodeSystem(abode_client, False)
    hass = Mock()
    entry = Mock()
    with patch("homeassistant.components.abode._start_reauth") as mock_start_reauth:
        _install_runtime_auth_guard(abode_system, hass, entry)

        with pytest.raises(AbodeAuthenticationException):
            abode_system.abode.send_request("GET", "/api/v1/panel")
        mock_start_reauth.assert_called_once()


def test_runtime_auth_guard_passthrough_for_non_auth() -> None:
    """Test send_request wrapper does not trigger reauth for non-auth failures."""
    abode_client = Mock()
    abode_client.send_request.side_effect = ValueError("boom")
    abode_system = AbodeSystem(abode_client, False)
    _install_runtime_auth_guard(abode_system, Mock(), Mock())

    with pytest.raises(ValueError):
        abode_system.abode.send_request("GET", "/api/v1/panel")

    ok_response = Mock(status_code=HTTPStatus.OK)
    ok_response.headers = {"Content-Type": "application/json"}
    ok_response.json.return_value = {"message": "ok"}
    abode_client = Mock()
    abode_client.send_request.return_value = ok_response
    abode_system = AbodeSystem(abode_client, False)
    _install_runtime_auth_guard(abode_system, Mock(), Mock())

    assert abode_system.abode.send_request("GET", "/api/v1/panel") is ok_response

"""Tests for the HTTP API for the cloud component."""
import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
from hass_nabucasa import thingtalk, voice
from hass_nabucasa.auth import Unauthenticated, UnknownError
from hass_nabucasa.const import STATE_CONNECTED
from jose import jwt
import pytest

from homeassistant.components.alexa import errors as alexa_errors
from homeassistant.components.alexa.entities import LightCapabilities
from homeassistant.components.cloud.const import DOMAIN
from homeassistant.components.google_assistant.helpers import GoogleEntity
from homeassistant.components.homeassistant import exposed_entities
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.location import LocationInfo

from . import mock_cloud, mock_cloud_prefs

from tests.components.google_assistant import MockConfig
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator, WebSocketGenerator

SUBSCRIPTION_INFO_URL = "https://api-test.hass.io/payments/subscription_info"


@pytest.fixture(name="mock_cloud_login")
def mock_cloud_login_fixture(hass, setup_api):
    """Mock cloud is logged in."""
    hass.data[DOMAIN].id_token = jwt.encode(
        {
            "email": "hello@home-assistant.io",
            "custom:sub-exp": "2018-01-03",
            "cognito:username": "abcdefghjkl",
        },
        "test",
    )


@pytest.fixture(autouse=True, name="setup_api")
def setup_api_fixture(hass, aioclient_mock):
    """Initialize HTTP API."""
    hass.loop.run_until_complete(
        mock_cloud(
            hass,
            {
                "mode": "development",
                "cognito_client_id": "cognito_client_id",
                "user_pool_id": "user_pool_id",
                "region": "region",
                "relayer_server": "relayer",
                "accounts_server": "api-test.hass.io",
                "google_actions": {"filter": {"include_domains": "light"}},
                "alexa": {
                    "filter": {"include_entities": ["light.kitchen", "switch.ac"]}
                },
            },
        )
    )
    return mock_cloud_prefs(hass)


@pytest.fixture(name="cloud_client")
def cloud_client_fixture(hass, hass_client):
    """Fixture that can fetch from the cloud client."""
    with patch("hass_nabucasa.Cloud._write_user_info"):
        yield hass.loop.run_until_complete(hass_client())


@pytest.fixture(name="mock_cognito")
def mock_cognito_fixture():
    """Mock warrant."""
    with patch("hass_nabucasa.auth.CognitoAuth._cognito") as mock_cog:
        yield mock_cog()


async def test_google_actions_sync(
    mock_cognito, mock_cloud_login, cloud_client
) -> None:
    """Test syncing Google Actions."""
    with patch(
        "hass_nabucasa.cloud_api.async_google_actions_request_sync",
        return_value=Mock(status=200),
    ) as mock_request_sync:
        req = await cloud_client.post("/api/cloud/google_actions/sync")
        assert req.status == HTTPStatus.OK
        assert len(mock_request_sync.mock_calls) == 1


async def test_google_actions_sync_fails(
    mock_cognito, mock_cloud_login, cloud_client
) -> None:
    """Test syncing Google Actions gone bad."""
    with patch(
        "hass_nabucasa.cloud_api.async_google_actions_request_sync",
        return_value=Mock(status=HTTPStatus.INTERNAL_SERVER_ERROR),
    ) as mock_request_sync:
        req = await cloud_client.post("/api/cloud/google_actions/sync")
        assert req.status == HTTPStatus.INTERNAL_SERVER_ERROR
        assert len(mock_request_sync.mock_calls) == 1


async def test_login_view(hass: HomeAssistant, cloud_client) -> None:
    """Test logging in when an assist pipeline is available."""
    hass.data["cloud"] = MagicMock(login=AsyncMock())
    await async_setup_component(hass, "stt", {})
    await async_setup_component(hass, "tts", {})

    with patch(
        "homeassistant.components.cloud.http_api.assist_pipeline.async_get_pipelines",
        return_value=[
            Mock(
                conversation_engine="homeassistant",
                id="12345",
                stt_engine=DOMAIN,
                tts_engine=DOMAIN,
            )
        ],
    ), patch(
        "homeassistant.components.cloud.http_api.assist_pipeline.async_create_default_pipeline",
    ) as create_pipeline_mock:
        req = await cloud_client.post(
            "/api/cloud/login", json={"email": "my_username", "password": "my_password"}
        )

    assert req.status == HTTPStatus.OK
    result = await req.json()
    assert result == {"success": True, "cloud_pipeline": None}
    create_pipeline_mock.assert_not_awaited()


async def test_login_view_create_pipeline(hass: HomeAssistant, cloud_client) -> None:
    """Test logging in when no assist pipeline is available."""
    hass.data["cloud"] = MagicMock(login=AsyncMock())
    await async_setup_component(hass, "stt", {})
    await async_setup_component(hass, "tts", {})

    with patch(
        "homeassistant.components.cloud.http_api.assist_pipeline.async_create_default_pipeline",
        return_value=AsyncMock(id="12345"),
    ) as create_pipeline_mock:
        req = await cloud_client.post(
            "/api/cloud/login", json={"email": "my_username", "password": "my_password"}
        )

    assert req.status == HTTPStatus.OK
    result = await req.json()
    assert result == {"success": True, "cloud_pipeline": "12345"}
    create_pipeline_mock.assert_awaited_once_with(hass, "cloud", "cloud")


async def test_login_view_create_pipeline_fail(
    hass: HomeAssistant, cloud_client
) -> None:
    """Test logging in when no assist pipeline is available."""
    hass.data["cloud"] = MagicMock(login=AsyncMock())
    await async_setup_component(hass, "stt", {})
    await async_setup_component(hass, "tts", {})

    with patch(
        "homeassistant.components.cloud.http_api.assist_pipeline.async_create_default_pipeline",
        return_value=None,
    ) as create_pipeline_mock:
        req = await cloud_client.post(
            "/api/cloud/login", json={"email": "my_username", "password": "my_password"}
        )

    assert req.status == HTTPStatus.OK
    result = await req.json()
    assert result == {"success": True, "cloud_pipeline": None}
    create_pipeline_mock.assert_awaited_once_with(hass, "cloud", "cloud")


async def test_login_view_random_exception(cloud_client) -> None:
    """Try logging in with invalid JSON."""
    with patch("hass_nabucasa.Cloud.login", side_effect=ValueError("Boom")):
        req = await cloud_client.post(
            "/api/cloud/login", json={"email": "my_username", "password": "my_password"}
        )
    assert req.status == HTTPStatus.BAD_GATEWAY
    resp = await req.json()
    assert resp == {"code": "valueerror", "message": "Unexpected error: Boom"}


async def test_login_view_invalid_json(cloud_client) -> None:
    """Try logging in with invalid JSON."""
    with patch("hass_nabucasa.auth.CognitoAuth.async_login") as mock_login:
        req = await cloud_client.post("/api/cloud/login", data="Not JSON")
    assert req.status == HTTPStatus.BAD_REQUEST
    assert len(mock_login.mock_calls) == 0


async def test_login_view_invalid_schema(cloud_client) -> None:
    """Try logging in with invalid schema."""
    with patch("hass_nabucasa.auth.CognitoAuth.async_login") as mock_login:
        req = await cloud_client.post("/api/cloud/login", json={"invalid": "schema"})
    assert req.status == HTTPStatus.BAD_REQUEST
    assert len(mock_login.mock_calls) == 0


async def test_login_view_request_timeout(cloud_client) -> None:
    """Test request timeout while trying to log in."""
    with patch(
        "hass_nabucasa.auth.CognitoAuth.async_login", side_effect=asyncio.TimeoutError
    ):
        req = await cloud_client.post(
            "/api/cloud/login", json={"email": "my_username", "password": "my_password"}
        )

    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_login_view_invalid_credentials(cloud_client) -> None:
    """Test logging in with invalid credentials."""
    with patch(
        "hass_nabucasa.auth.CognitoAuth.async_login", side_effect=Unauthenticated
    ):
        req = await cloud_client.post(
            "/api/cloud/login", json={"email": "my_username", "password": "my_password"}
        )

    assert req.status == HTTPStatus.UNAUTHORIZED


async def test_login_view_unknown_error(cloud_client) -> None:
    """Test unknown error while logging in."""
    with patch("hass_nabucasa.auth.CognitoAuth.async_login", side_effect=UnknownError):
        req = await cloud_client.post(
            "/api/cloud/login", json={"email": "my_username", "password": "my_password"}
        )

    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_logout_view(hass: HomeAssistant, cloud_client) -> None:
    """Test logging out."""
    cloud = hass.data["cloud"] = MagicMock()
    cloud.logout = AsyncMock(return_value=None)
    req = await cloud_client.post("/api/cloud/logout")
    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data == {"message": "ok"}
    assert len(cloud.logout.mock_calls) == 1


async def test_logout_view_request_timeout(hass: HomeAssistant, cloud_client) -> None:
    """Test timeout while logging out."""
    cloud = hass.data["cloud"] = MagicMock()
    cloud.logout.side_effect = asyncio.TimeoutError
    req = await cloud_client.post("/api/cloud/logout")
    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_logout_view_unknown_error(hass: HomeAssistant, cloud_client) -> None:
    """Test unknown error while logging out."""
    cloud = hass.data["cloud"] = MagicMock()
    cloud.logout.side_effect = UnknownError
    req = await cloud_client.post("/api/cloud/logout")
    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_register_view_no_location(mock_cognito, cloud_client) -> None:
    """Test register without location."""
    with patch(
        "homeassistant.components.cloud.http_api.async_detect_location_info",
        return_value=None,
    ):
        req = await cloud_client.post(
            "/api/cloud/register",
            json={"email": "hello@bla.com", "password": "falcon42"},
        )
    assert req.status == HTTPStatus.OK
    assert len(mock_cognito.register.mock_calls) == 1
    call = mock_cognito.register.mock_calls[0]
    result_email, result_pass = call.args
    assert result_email == "hello@bla.com"
    assert result_pass == "falcon42"
    assert call.kwargs["client_metadata"] is None


async def test_register_view_with_location(mock_cognito, cloud_client) -> None:
    """Test register with location."""
    with patch(
        "homeassistant.components.cloud.http_api.async_detect_location_info",
        return_value=LocationInfo(
            **{
                "country_code": "XX",
                "zip_code": "12345",
                "region_code": "GH",
                "ip": "1.2.3.4",
                "city": "Gotham",
                "region_name": "Gotham",
                "time_zone": "Earth/Gotham",
                "currency": "XXX",
                "latitude": "12.34567",
                "longitude": "12.34567",
                "use_metric": True,
            }
        ),
    ):
        req = await cloud_client.post(
            "/api/cloud/register",
            json={"email": "hello@bla.com", "password": "falcon42"},
        )
    assert req.status == HTTPStatus.OK
    assert len(mock_cognito.register.mock_calls) == 1
    call = mock_cognito.register.mock_calls[0]
    result_email, result_pass = call.args
    assert result_email == "hello@bla.com"
    assert result_pass == "falcon42"
    assert call.kwargs["client_metadata"] == {
        "NC_COUNTRY_CODE": "XX",
        "NC_REGION_CODE": "GH",
        "NC_ZIP_CODE": "12345",
    }


async def test_register_view_bad_data(mock_cognito, cloud_client) -> None:
    """Test logging out."""
    req = await cloud_client.post(
        "/api/cloud/register", json={"email": "hello@bla.com", "not_password": "falcon"}
    )
    assert req.status == HTTPStatus.BAD_REQUEST
    assert len(mock_cognito.logout.mock_calls) == 0


async def test_register_view_request_timeout(mock_cognito, cloud_client) -> None:
    """Test timeout while logging out."""
    mock_cognito.register.side_effect = asyncio.TimeoutError
    req = await cloud_client.post(
        "/api/cloud/register", json={"email": "hello@bla.com", "password": "falcon42"}
    )
    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_register_view_unknown_error(mock_cognito, cloud_client) -> None:
    """Test unknown error while logging out."""
    mock_cognito.register.side_effect = UnknownError
    req = await cloud_client.post(
        "/api/cloud/register", json={"email": "hello@bla.com", "password": "falcon42"}
    )
    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_forgot_password_view(mock_cognito, cloud_client) -> None:
    """Test logging out."""
    req = await cloud_client.post(
        "/api/cloud/forgot_password", json={"email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.OK
    assert len(mock_cognito.initiate_forgot_password.mock_calls) == 1


async def test_forgot_password_view_bad_data(mock_cognito, cloud_client) -> None:
    """Test logging out."""
    req = await cloud_client.post(
        "/api/cloud/forgot_password", json={"not_email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.BAD_REQUEST
    assert len(mock_cognito.initiate_forgot_password.mock_calls) == 0


async def test_forgot_password_view_request_timeout(mock_cognito, cloud_client) -> None:
    """Test timeout while logging out."""
    mock_cognito.initiate_forgot_password.side_effect = asyncio.TimeoutError
    req = await cloud_client.post(
        "/api/cloud/forgot_password", json={"email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_forgot_password_view_unknown_error(mock_cognito, cloud_client) -> None:
    """Test unknown error while logging out."""
    mock_cognito.initiate_forgot_password.side_effect = UnknownError
    req = await cloud_client.post(
        "/api/cloud/forgot_password", json={"email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_forgot_password_view_aiohttp_error(mock_cognito, cloud_client) -> None:
    """Test unknown error while logging out."""
    mock_cognito.initiate_forgot_password.side_effect = aiohttp.ClientResponseError(
        Mock(), Mock()
    )
    req = await cloud_client.post(
        "/api/cloud/forgot_password", json={"email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_resend_confirm_view(mock_cognito, cloud_client) -> None:
    """Test logging out."""
    req = await cloud_client.post(
        "/api/cloud/resend_confirm", json={"email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.OK
    assert len(mock_cognito.client.resend_confirmation_code.mock_calls) == 1


async def test_resend_confirm_view_bad_data(mock_cognito, cloud_client) -> None:
    """Test logging out."""
    req = await cloud_client.post(
        "/api/cloud/resend_confirm", json={"not_email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.BAD_REQUEST
    assert len(mock_cognito.client.resend_confirmation_code.mock_calls) == 0


async def test_resend_confirm_view_request_timeout(mock_cognito, cloud_client) -> None:
    """Test timeout while logging out."""
    mock_cognito.client.resend_confirmation_code.side_effect = asyncio.TimeoutError
    req = await cloud_client.post(
        "/api/cloud/resend_confirm", json={"email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_resend_confirm_view_unknown_error(mock_cognito, cloud_client) -> None:
    """Test unknown error while logging out."""
    mock_cognito.client.resend_confirmation_code.side_effect = UnknownError
    req = await cloud_client.post(
        "/api/cloud/resend_confirm", json={"email": "hello@bla.com"}
    )
    assert req.status == HTTPStatus.BAD_GATEWAY


async def test_websocket_status(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_cloud_fixture,
    mock_cloud_login,
) -> None:
    """Test querying the status."""
    hass.data[DOMAIN].iot.state = STATE_CONNECTED
    client = await hass_ws_client(hass)

    with patch.dict(
        "homeassistant.components.google_assistant.const.DOMAIN_TO_GOOGLE_TYPES",
        {"light": None},
        clear=True,
    ), patch.dict(
        "homeassistant.components.alexa.entities.ENTITY_ADAPTERS",
        {"switch": None},
        clear=True,
    ):
        await client.send_json({"id": 5, "type": "cloud/status"})
        response = await client.receive_json()
    assert response["result"] == {
        "logged_in": True,
        "email": "hello@home-assistant.io",
        "cloud": "connected",
        "cloud_last_disconnect_reason": None,
        "prefs": {
            "alexa_enabled": True,
            "cloudhooks": {},
            "google_enabled": True,
            "google_secure_devices_pin": None,
            "google_default_expose": None,
            "alexa_default_expose": None,
            "alexa_report_state": True,
            "google_report_state": True,
            "remote_enabled": False,
            "tts_default_voice": ["en-US", "female"],
        },
        "alexa_entities": {
            "include_domains": [],
            "include_entity_globs": [],
            "include_entities": ["light.kitchen", "switch.ac"],
            "exclude_domains": [],
            "exclude_entity_globs": [],
            "exclude_entities": [],
        },
        "alexa_registered": False,
        "google_entities": {
            "include_domains": ["light"],
            "include_entity_globs": [],
            "include_entities": [],
            "exclude_domains": [],
            "exclude_entity_globs": [],
            "exclude_entities": [],
        },
        "google_registered": False,
        "google_local_connected": False,
        "remote_domain": None,
        "remote_connected": False,
        "remote_certificate_status": None,
        "remote_certificate": None,
        "http_use_ssl": False,
        "active_subscription": False,
    }


async def test_websocket_status_not_logged_in(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test querying the status."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "cloud/status"})
    response = await client.receive_json()
    assert response["result"] == {
        "logged_in": False,
        "cloud": "disconnected",
        "http_use_ssl": False,
    }


async def test_websocket_subscription_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_auth,
    mock_cloud_login,
) -> None:
    """Test querying the status and connecting because valid account."""
    aioclient_mock.get(SUBSCRIPTION_INFO_URL, json={"provider": "stripe"})
    client = await hass_ws_client(hass)

    with patch("hass_nabucasa.auth.CognitoAuth.async_renew_access_token") as mock_renew:
        await client.send_json({"id": 5, "type": "cloud/subscription"})
        response = await client.receive_json()
    assert response["result"] == {"provider": "stripe"}
    assert len(mock_renew.mock_calls) == 1


async def test_websocket_subscription_fail(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_auth,
    mock_cloud_login,
) -> None:
    """Test querying the status."""
    aioclient_mock.get(SUBSCRIPTION_INFO_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "cloud/subscription"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "request_failed"


async def test_websocket_subscription_not_logged_in(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test querying the status."""
    client = await hass_ws_client(hass)
    with patch(
        "hass_nabucasa.cloud_api.async_subscription_info",
        return_value={"return": "value"},
    ):
        await client.send_json({"id": 5, "type": "cloud/subscription"})
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "not_logged_in"


async def test_websocket_update_preferences(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test updating preference."""
    assert setup_api.google_enabled
    assert setup_api.alexa_enabled
    assert setup_api.google_secure_devices_pin is None
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "cloud/update_prefs",
            "alexa_enabled": False,
            "google_enabled": False,
            "google_secure_devices_pin": "1234",
            "tts_default_voice": ["en-GB", "male"],
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert not setup_api.google_enabled
    assert not setup_api.alexa_enabled
    assert setup_api.google_secure_devices_pin == "1234"
    assert setup_api.tts_default_voice == ("en-GB", "male")


async def test_websocket_update_preferences_alexa_report_state(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test updating alexa_report_state sets alexa authorized."""
    client = await hass_ws_client(hass)

    with patch(
        (
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig"
            ".async_get_access_token"
        ),
    ), patch(
        "homeassistant.components.cloud.alexa_config.CloudAlexaConfig.set_authorized"
    ) as set_authorized_mock:
        set_authorized_mock.assert_not_called()
        await client.send_json(
            {"id": 5, "type": "cloud/update_prefs", "alexa_report_state": True}
        )
        response = await client.receive_json()
        set_authorized_mock.assert_called_once_with(True)

    assert response["success"]


async def test_websocket_update_preferences_require_relink(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test updating preference requires relink."""
    client = await hass_ws_client(hass)

    with patch(
        (
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig"
            ".async_get_access_token"
        ),
        side_effect=alexa_errors.RequireRelink,
    ), patch(
        "homeassistant.components.cloud.alexa_config.CloudAlexaConfig.set_authorized"
    ) as set_authorized_mock:
        set_authorized_mock.assert_not_called()
        await client.send_json(
            {"id": 5, "type": "cloud/update_prefs", "alexa_report_state": True}
        )
        response = await client.receive_json()
        set_authorized_mock.assert_called_once_with(False)

    assert not response["success"]
    assert response["error"]["code"] == "alexa_relink"


async def test_websocket_update_preferences_no_token(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test updating preference no token available."""
    client = await hass_ws_client(hass)

    with patch(
        (
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig"
            ".async_get_access_token"
        ),
        side_effect=alexa_errors.NoTokenAvailable,
    ), patch(
        "homeassistant.components.cloud.alexa_config.CloudAlexaConfig.set_authorized"
    ) as set_authorized_mock:
        set_authorized_mock.assert_not_called()
        await client.send_json(
            {"id": 5, "type": "cloud/update_prefs", "alexa_report_state": True}
        )
        response = await client.receive_json()
        set_authorized_mock.assert_called_once_with(False)

    assert not response["success"]
    assert response["error"]["code"] == "alexa_relink"


async def test_enabling_webhook(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api, mock_cloud_login
) -> None:
    """Test we call right code to enable webhooks."""
    client = await hass_ws_client(hass)
    with patch(
        "hass_nabucasa.cloudhooks.Cloudhooks.async_create", return_value={}
    ) as mock_enable:
        await client.send_json(
            {"id": 5, "type": "cloud/cloudhook/create", "webhook_id": "mock-webhook-id"}
        )
        response = await client.receive_json()
    assert response["success"]

    assert len(mock_enable.mock_calls) == 1
    assert mock_enable.mock_calls[0][1][0] == "mock-webhook-id"


async def test_disabling_webhook(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api, mock_cloud_login
) -> None:
    """Test we call right code to disable webhooks."""
    client = await hass_ws_client(hass)
    with patch("hass_nabucasa.cloudhooks.Cloudhooks.async_delete") as mock_disable:
        await client.send_json(
            {"id": 5, "type": "cloud/cloudhook/delete", "webhook_id": "mock-webhook-id"}
        )
        response = await client.receive_json()
    assert response["success"]

    assert len(mock_disable.mock_calls) == 1
    assert mock_disable.mock_calls[0][1][0] == "mock-webhook-id"


async def test_enabling_remote(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api, mock_cloud_login
) -> None:
    """Test we call right code to enable remote UI."""
    client = await hass_ws_client(hass)
    cloud = hass.data[DOMAIN]

    with patch("hass_nabucasa.remote.RemoteUI.connect") as mock_connect:
        await client.send_json({"id": 5, "type": "cloud/remote/connect"})
        response = await client.receive_json()
    assert response["success"]
    assert cloud.client.remote_autostart

    assert len(mock_connect.mock_calls) == 1

    with patch("hass_nabucasa.remote.RemoteUI.disconnect") as mock_disconnect:
        await client.send_json({"id": 6, "type": "cloud/remote/disconnect"})
        response = await client.receive_json()
    assert response["success"]
    assert not cloud.client.remote_autostart

    assert len(mock_disconnect.mock_calls) == 1


async def test_list_google_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test that we can list Google entities."""
    client = await hass_ws_client(hass)
    entity = GoogleEntity(
        hass, MockConfig(should_expose=lambda *_: False), State("light.kitchen", "on")
    )
    entity2 = GoogleEntity(
        hass,
        MockConfig(should_expose=lambda *_: True, should_2fa=lambda *_: False),
        State("cover.garage", "open", {"device_class": "garage"}),
    )
    with patch(
        "homeassistant.components.google_assistant.helpers.async_get_entities",
        return_value=[entity, entity2],
    ):
        await client.send_json_auto_id({"type": "cloud/google_assistant/entities"})
        response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 2
    assert response["result"][0] == {
        "entity_id": "light.kitchen",
        "might_2fa": False,
        "traits": ["action.devices.traits.OnOff"],
    }
    assert response["result"][1] == {
        "entity_id": "cover.garage",
        "might_2fa": True,
        "traits": ["action.devices.traits.OpenClose"],
    }

    # Add the entities to the entity registry
    entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    entity_registry.async_get_or_create(
        "cover", "test", "unique", suggested_object_id="garage"
    )

    with patch(
        "homeassistant.components.google_assistant.helpers.async_get_entities",
        return_value=[entity, entity2],
    ):
        await client.send_json_auto_id({"type": "cloud/google_assistant/entities"})
        response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 2
    assert response["result"][0] == {
        "entity_id": "light.kitchen",
        "might_2fa": False,
        "traits": ["action.devices.traits.OnOff"],
    }
    assert response["result"][1] == {
        "entity_id": "cover.garage",
        "might_2fa": True,
        "traits": ["action.devices.traits.OpenClose"],
    }


async def test_get_google_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test that we can get a Google entity."""
    client = await hass_ws_client(hass)

    # Test getting an unknown entity
    await client.send_json_auto_id(
        {"type": "cloud/google_assistant/entities/get", "entity_id": "light.kitchen"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "not_found",
        "message": "light.kitchen unknown",
    }

    # Test getting a blocked entity
    entity_registry.async_get_or_create(
        "group", "test", "unique", suggested_object_id="all_locks"
    )
    hass.states.async_set("group.all_locks", "bla")
    await client.send_json_auto_id(
        {"type": "cloud/google_assistant/entities/get", "entity_id": "group.all_locks"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "not_supported",
        "message": "group.all_locks not supported by Google assistant",
    }

    entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("cover.garage", "open", {"device_class": "garage"})

    await client.send_json_auto_id(
        {"type": "cloud/google_assistant/entities/get", "entity_id": "light.kitchen"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "disable_2fa": None,
        "entity_id": "light.kitchen",
        "might_2fa": False,
        "traits": ["action.devices.traits.OnOff"],
    }

    await client.send_json_auto_id(
        {"type": "cloud/google_assistant/entities/get", "entity_id": "cover.garage"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "disable_2fa": None,
        "entity_id": "cover.garage",
        "might_2fa": True,
        "traits": ["action.devices.traits.OpenClose"],
    }

    # Set the disable 2fa flag
    await client.send_json_auto_id(
        {
            "type": "cloud/google_assistant/entities/update",
            "entity_id": "cover.garage",
            "disable_2fa": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {"type": "cloud/google_assistant/entities/get", "entity_id": "cover.garage"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "disable_2fa": True,
        "entity_id": "cover.garage",
        "might_2fa": True,
        "traits": ["action.devices.traits.OpenClose"],
    }


async def test_update_google_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test that we can update config of a Google entity."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "cloud/google_assistant/entities/update",
            "entity_id": "light.kitchen",
            "disable_2fa": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json_auto_id(
        {
            "type": "homeassistant/expose_entity",
            "assistants": ["cloud.google_assistant"],
            "entity_ids": ["light.kitchen"],
            "should_expose": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    assert exposed_entities.async_get_entity_settings(hass, "light.kitchen") == {
        "cloud.google_assistant": {"disable_2fa": False, "should_expose": False}
    }


async def test_list_alexa_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test that we can list Alexa entities."""
    client = await hass_ws_client(hass)
    entity = LightCapabilities(
        hass, MagicMock(entity_config={}), State("light.kitchen", "on")
    )
    with patch(
        "homeassistant.components.alexa.entities.async_get_entities",
        return_value=[entity],
    ):
        await client.send_json_auto_id({"id": 5, "type": "cloud/alexa/entities"})
        response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert response["result"][0] == {
        "entity_id": "light.kitchen",
        "display_categories": ["LIGHT"],
        "interfaces": ["Alexa.PowerController", "Alexa.EndpointHealth", "Alexa"],
    }

    # Add the entity to the entity registry
    entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )

    with patch(
        "homeassistant.components.alexa.entities.async_get_entities",
        return_value=[entity],
    ):
        await client.send_json_auto_id({"type": "cloud/alexa/entities"})
        response = await client.receive_json()
    assert response["success"]
    assert len(response["result"]) == 1
    assert response["result"][0] == {
        "entity_id": "light.kitchen",
        "display_categories": ["LIGHT"],
        "interfaces": ["Alexa.PowerController", "Alexa.EndpointHealth", "Alexa"],
    }


async def test_get_alexa_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test that we can get an Alexa entity."""
    client = await hass_ws_client(hass)

    # Test getting an unknown entity
    await client.send_json_auto_id(
        {"type": "cloud/alexa/entities/get", "entity_id": "light.kitchen"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    # Test getting an unknown sensor
    await client.send_json_auto_id(
        {"type": "cloud/alexa/entities/get", "entity_id": "sensor.temperature"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "not_supported",
        "message": "sensor.temperature not supported by Alexa",
    }

    # Test getting a blocked entity
    entity_registry.async_get_or_create(
        "group", "test", "unique", suggested_object_id="all_locks"
    )
    hass.states.async_set("group.all_locks", "bla")
    await client.send_json_auto_id(
        {"type": "cloud/alexa/entities/get", "entity_id": "group.all_locks"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "not_supported",
        "message": "group.all_locks not supported by Alexa",
    }

    entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    entity_registry.async_get_or_create(
        "water_heater", "test", "unique", suggested_object_id="basement"
    )

    await client.send_json_auto_id(
        {"type": "cloud/alexa/entities/get", "entity_id": "light.kitchen"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await client.send_json_auto_id(
        {"type": "cloud/alexa/entities/get", "entity_id": "water_heater.basement"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "not_supported",
        "message": "water_heater.basement not supported by Alexa",
    }


async def test_update_alexa_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    setup_api,
    mock_cloud_login,
) -> None:
    """Test that we can update config of an Alexa entity."""
    entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "homeassistant/expose_entity",
            "assistants": ["cloud.alexa"],
            "entity_ids": [entry.entity_id],
            "should_expose": False,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert exposed_entities.async_get_entity_settings(hass, entry.entity_id) == {
        "cloud.alexa": {"should_expose": False}
    }


async def test_sync_alexa_entities_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api, mock_cloud_login
) -> None:
    """Test that timeout syncing Alexa entities."""
    client = await hass_ws_client(hass)
    with patch(
        (
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig"
            ".async_sync_entities"
        ),
        side_effect=asyncio.TimeoutError,
    ):
        await client.send_json({"id": 5, "type": "cloud/alexa/sync"})
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "timeout"


async def test_sync_alexa_entities_no_token(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api, mock_cloud_login
) -> None:
    """Test sync Alexa entities when we have no token."""
    client = await hass_ws_client(hass)
    with patch(
        (
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig"
            ".async_sync_entities"
        ),
        side_effect=alexa_errors.NoTokenAvailable,
    ):
        await client.send_json({"id": 5, "type": "cloud/alexa/sync"})
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "alexa_relink"


async def test_enable_alexa_state_report_fail(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api, mock_cloud_login
) -> None:
    """Test enable Alexa entities state reporting when no token available."""
    client = await hass_ws_client(hass)
    with patch(
        (
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig"
            ".async_sync_entities"
        ),
        side_effect=alexa_errors.NoTokenAvailable,
    ):
        await client.send_json({"id": 5, "type": "cloud/alexa/sync"})
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "alexa_relink"


async def test_thingtalk_convert(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api
) -> None:
    """Test that we can convert a query."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.cloud.http_api.thingtalk.async_convert",
        return_value={"hello": "world"},
    ):
        await client.send_json(
            {"id": 5, "type": "cloud/thingtalk/convert", "query": "some-data"}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"hello": "world"}


async def test_thingtalk_convert_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api
) -> None:
    """Test that we can convert a query."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.cloud.http_api.thingtalk.async_convert",
        side_effect=asyncio.TimeoutError,
    ):
        await client.send_json(
            {"id": 5, "type": "cloud/thingtalk/convert", "query": "some-data"}
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "timeout"


async def test_thingtalk_convert_internal(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api
) -> None:
    """Test that we can convert a query."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.cloud.http_api.thingtalk.async_convert",
        side_effect=thingtalk.ThingTalkConversionError("Did not understand"),
    ):
        await client.send_json(
            {"id": 5, "type": "cloud/thingtalk/convert", "query": "some-data"}
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"
    assert response["error"]["message"] == "Did not understand"


async def test_tts_info(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup_api
) -> None:
    """Test that we can get TTS info."""
    # Verify the format is as expected
    assert voice.MAP_VOICE[("en-US", voice.Gender.FEMALE)] == "JennyNeural"

    client = await hass_ws_client(hass)

    with patch.dict(
        "homeassistant.components.cloud.http_api.MAP_VOICE",
        {
            ("en-US", voice.Gender.MALE): "GuyNeural",
            ("en-US", voice.Gender.FEMALE): "JennyNeural",
        },
        clear=True,
    ):
        await client.send_json({"id": 5, "type": "cloud/tts/info"})
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"languages": [["en-US", "male"], ["en-US", "female"]]}


@pytest.mark.parametrize(
    ("endpoint", "data"),
    [
        ("/api/cloud/forgot_password", {"email": "fake@example.com"}),
        ("/api/cloud/google_actions/sync", None),
        ("/api/cloud/login", {"email": "fake@example.com", "password": "secret"}),
        ("/api/cloud/logout", None),
        ("/api/cloud/register", {"email": "fake@example.com", "password": "secret"}),
        ("/api/cloud/resend_confirm", {"email": "fake@example.com"}),
    ],
)
async def test_api_calls_require_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
    endpoint: str,
    data: dict[str, Any] | None,
) -> None:
    """Test cloud APIs endpoints do not work as a normal user."""
    client = await hass_client(hass_read_only_access_token)
    resp = await client.post(endpoint, json=data)

    assert resp.status == HTTPStatus.UNAUTHORIZED

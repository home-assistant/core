"""Test that the integration is initialized correctly."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
import threading
import time
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientConnectionError, ClientResponseError
from freezegun.api import FrozenDateTimeFactory
import jwt
from place.config import OAUTH2_TOKEN_URL
from place.errors import (
    PlaceCredentialExchangeAuthError,
    PlaceCredentialExchangeConnectionError,
    PlaceFulfillmentError,
    PlaceMqttConnectionError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gentex_place.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestTransientError,
)

from . import TEST_ID_JWT, TEST_JWT_KEY, setup_integration


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_provider.enable.assert_awaited_once()
    mock_provider.discover.assert_awaited_once()
    mock_get_iot_credentials.assert_called_once_with(TEST_ID_JWT, "mock-access-token")
    mock_mqtt_client.connect.assert_called_once()


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_setup_seeds_shadow_from_discover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that initial shadow state is seeded from device discovery."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    assert "thing-001" in coordinator.data
    shadow = coordinator.data["thing-001"]
    assert shadow.co_alarm_status.value == 0
    assert shadow.heat_alarm_status.value == 0
    assert shadow.smoke_alarm_status.value == 0


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test the entry can be loaded and unloaded."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_mqtt_client.disconnect.assert_called_once()


@pytest.mark.usefixtures(
    "mock_provider",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a token refresh failure raises ConfigEntryAuthFailed."""
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        status=HTTPStatus.UNAUTHORIZED,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_provider", "mock_mqtt_client")
async def test_setup_credential_exchange_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_iot_credentials: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An authorization failure during credential exchange fails setup."""
    mock_get_iot_credentials.side_effect = PlaceCredentialExchangeAuthError()

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert "could not authenticate" in caplog.text


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_provider")
async def test_setup_credential_exchange_connection_failure_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client_cls: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A transient credential exchange failure retries and recovers."""
    mock_get_iot_credentials.side_effect = [
        PlaceCredentialExchangeConnectionError(),
        mock_get_iot_credentials.return_value,
    ]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    mock_mqtt_client_cls.assert_not_called()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_get_iot_credentials.call_count == 2
    mock_mqtt_client_cls.assert_called_once()


@pytest.mark.usefixtures(
    "mock_provider",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_setup_auth_refresh_missing_access_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a refresh response without an access token fails setup."""
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        status=HTTPStatus.OK,
        json={},
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "id_token",
    [
        pytest.param(None, id="missing"),
        pytest.param("invalid", id="malformed"),
        pytest.param(jwt.encode({}, TEST_JWT_KEY), id="missing-expiry"),
        pytest.param(jwt.encode({"exp": 1}, TEST_JWT_KEY), id="expired"),
    ],
)
@pytest.mark.usefixtures(
    "mock_provider", "mock_get_iot_credentials", "mock_mqtt_client"
)
async def test_setup_auth_refresh_invalid_id_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    id_token: str | None,
) -> None:
    """Reject invalid ID tokens instead of retaining the old token."""
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={"access_token": "new-access", "id_token": id_token, "expires_in": 3600},
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_provider")
async def test_reconnect_credentials_valid_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client_cls: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Reconnect exchanges current tokens without an unnecessary OAuth refresh."""
    await setup_integration(hass, mock_config_entry)
    aioclient_mock.clear_requests()
    credentials_provider = mock_mqtt_client_cls.call_args.kwargs["credentials_provider"]

    credentials = await hass.async_add_executor_job(credentials_provider)

    assert credentials is mock_get_iot_credentials.return_value
    assert aioclient_mock.call_count == 0
    assert mock_get_iot_credentials.call_count == 2
    mock_get_iot_credentials.assert_called_with(TEST_ID_JWT, "mock-access-token")


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_provider")
async def test_reconnect_credentials_expired_id_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client_cls: MagicMock,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Refresh both tokens when the ID token expires before the access token."""
    await setup_integration(hass, mock_config_entry)
    initial_id = jwt.encode({"exp": int(time.time()) + 60}, TEST_JWT_KEY)
    refreshed_id = jwt.encode({"exp": 9999999998}, TEST_JWT_KEY)
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={"access_token": "access-1", "id_token": initial_id, "expires_in": 3600},
    )
    credentials_provider = mock_mqtt_client_cls.call_args.kwargs["credentials_provider"]
    token = {**mock_config_entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": token}
    )
    await hass.async_add_executor_job(credentials_provider)
    assert (
        mock_config_entry.data["token"]["expires_at"]
        == jwt.decode(initial_id, options={"verify_signature": False})["exp"]
    )

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={
            "access_token": "access-2",
            "id_token": refreshed_id,
            "expires_in": 3600,
        },
    )
    freezer.tick(timedelta(seconds=45))
    await hass.async_add_executor_job(credentials_provider)

    assert mock_config_entry.data["token"]["id_token"] == refreshed_id
    mock_get_iot_credentials.assert_called_with(refreshed_id, "access-2")


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_provider")
async def test_reconnect_token_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client_cls: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A transient OAuth failure does not exchange stale tokens."""
    await setup_integration(hass, mock_config_entry)
    credentials_provider = mock_mqtt_client_cls.call_args.kwargs["credentials_provider"]
    token = {**mock_config_entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": token}
    )
    aioclient_mock.clear_requests()
    aioclient_mock.post(OAUTH2_TOKEN_URL, status=HTTPStatus.SERVICE_UNAVAILABLE)

    with pytest.raises(OAuth2TokenRequestTransientError):
        await hass.async_add_executor_job(credentials_provider)
    assert mock_get_iot_credentials.call_count == 1

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={"access_token": "new", "id_token": TEST_ID_JWT, "expires_in": 3600},
    )
    await hass.async_add_executor_job(credentials_provider)
    mock_get_iot_credentials.assert_called_with(TEST_ID_JWT, "new")


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_provider")
async def test_reconnect_token_refresh_missing_id_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client_cls: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A refresh without an ID token never reuses or stores the old token."""
    await setup_integration(hass, mock_config_entry)
    credentials_provider = mock_mqtt_client_cls.call_args.kwargs["credentials_provider"]
    token = {**mock_config_entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": token}
    )
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN_URL, json={"access_token": "new", "expires_in": 3600}
    )

    with pytest.raises(OAuth2TokenRequestConnectionError):
        await hass.async_add_executor_job(credentials_provider)

    assert mock_config_entry.data["token"] == token
    assert mock_get_iot_credentials.call_count == 1


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_provider")
async def test_reconnect_credential_exchange_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client_cls: MagicMock,
) -> None:
    """An AWS credential exchange failure propagates to the MQTT library."""
    await setup_integration(hass, mock_config_entry)
    credentials_provider = mock_mqtt_client_cls.call_args.kwargs["credentials_provider"]
    mock_get_iot_credentials.side_effect = OSError("unavailable")

    with pytest.raises(OSError, match="unavailable"):
        await hass.async_add_executor_job(credentials_provider)


@pytest.mark.usefixtures(
    "aioclient_mock_fixture", "mock_provider", "mock_get_iot_credentials"
)
async def test_unload_during_reconnect_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client_cls: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Unloading leaves the event loop free to finish an in-flight refresh."""
    await setup_integration(hass, mock_config_entry)
    credentials_provider = mock_mqtt_client_cls.call_args.kwargs["credentials_provider"]
    token = {**mock_config_entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": token}
    )
    started = asyncio.Event()
    release = asyncio.Event()
    finished = threading.Event()
    stopping = threading.Event()
    response = aioclient_mock.request(
        "post",
        OAUTH2_TOKEN_URL,
        json={"access_token": "new", "id_token": TEST_ID_JWT, "expires_in": 3600},
    )

    async def delayed_response(*args: object) -> object:
        started.set()
        await release.wait()
        return response

    aioclient_mock.clear_requests()
    aioclient_mock.post(OAUTH2_TOKEN_URL, side_effect=delayed_response)

    def reconnect() -> None:
        try:
            credentials_provider()
        finally:
            finished.set()

    def stop_loop() -> None:
        stopping.set()
        assert finished.wait(5)

    mock_mqtt_client_cls.return_value.loop_stop.side_effect = stop_loop
    reconnect_task = asyncio.create_task(asyncio.to_thread(reconnect))
    await asyncio.wait_for(started.wait(), 5)
    unload_task = asyncio.create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    assert await asyncio.to_thread(stopping.wait, 5)
    release.set()
    await asyncio.wait_for(asyncio.gather(reconnect_task, unload_task), 5)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures(
    "mock_provider",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_setup_auth_transient_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a transient token refresh failure retries setup."""
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        status=HTTPStatus.SERVICE_UNAVAILABLE,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.fixture
def token_request_timeout(aioclient_mock: AiohttpClientMocker) -> None:
    """Time out while requesting a token."""
    aioclient_mock.post(OAUTH2_TOKEN_URL, exc=TimeoutError())


@pytest.fixture
def token_response_timeout(aioclient_mock: AiohttpClientMocker) -> None:
    """Time out while reading a token response."""
    response = aioclient_mock.request("post", OAUTH2_TOKEN_URL)
    response.json = AsyncMock(side_effect=TimeoutError())


@pytest.fixture
def token_timeout(request: pytest.FixtureRequest) -> None:
    """Set up the requested token timeout."""
    request.getfixturevalue(request.param)


@pytest.mark.parametrize(
    "token_timeout",
    [
        pytest.param("token_request_timeout", id="request"),
        pytest.param("token_response_timeout", id="response-body"),
    ],
    indirect=True,
)
@pytest.mark.usefixtures(
    "token_timeout", "mock_provider", "mock_get_iot_credentials", "mock_mqtt_client"
)
async def test_setup_auth_timeout_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A token timeout retries setup and recovers when the service responds."""
    original_token = mock_config_entry.data["token"]
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.data["token"] == original_token
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={"access_token": "new", "id_token": TEST_ID_JWT, "expires_in": 3600},
    )
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data["token"]["access_token"] == "new"


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_provider")
async def test_reconnect_token_refresh_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_iot_credentials: MagicMock,
    mock_mqtt_client_cls: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A token timeout cannot cause reconnect to exchange stale credentials."""
    await setup_integration(hass, mock_config_entry)
    credentials_provider = mock_mqtt_client_cls.call_args.kwargs["credentials_provider"]
    token = {**mock_config_entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": token}
    )
    aioclient_mock.clear_requests()
    aioclient_mock.post(OAUTH2_TOKEN_URL, exc=TimeoutError())

    with pytest.raises(OAuth2TokenRequestConnectionError):
        await hass.async_add_executor_job(credentials_provider)

    assert mock_config_entry.data["token"] == token
    assert mock_get_iot_credentials.call_count == 1

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN_URL,
        json={"access_token": "new", "id_token": TEST_ID_JWT, "expires_in": 3600},
    )
    await hass.async_add_executor_job(credentials_provider)
    mock_get_iot_credentials.assert_called_with(TEST_ID_JWT, "new")


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
@pytest.mark.parametrize("method", ["enable", "discover"])
@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        pytest.param(HTTPStatus.UNAUTHORIZED, ConfigEntryState.SETUP_ERROR, id="401"),
        pytest.param(HTTPStatus.FORBIDDEN, ConfigEntryState.SETUP_ERROR, id="403"),
        pytest.param(HTTPStatus.BAD_REQUEST, ConfigEntryState.SETUP_RETRY, id="400"),
        pytest.param(
            HTTPStatus.TOO_MANY_REQUESTS, ConfigEntryState.SETUP_RETRY, id="429"
        ),
        pytest.param(
            HTTPStatus.SERVICE_UNAVAILABLE, ConfigEntryState.SETUP_RETRY, id="503"
        ),
    ],
)
async def test_setup_fulfillment_http_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    method: str,
    status: HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Map fulfillment API HTTP errors to the appropriate setup state."""
    getattr(mock_provider, method).side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=status
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
@pytest.mark.parametrize("method", ["enable", "discover"])
async def test_setup_fulfillment_rate_limit_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """A fulfillment API rate limit is retried and setup recovers."""
    provider_method = getattr(mock_provider, method)
    provider_method.side_effect = [
        ClientResponseError(
            request_info=MagicMock(), history=(), status=HTTPStatus.TOO_MANY_REQUESTS
        ),
        provider_method.return_value,
    ]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert provider_method.await_count == 2


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_setup_enable_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
) -> None:
    """Test that a connection error from the fulfillment API retries setup."""
    mock_provider.enable.side_effect = ClientConnectionError()

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_setup_enable_fulfillment_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_provider: AsyncMock,
) -> None:
    """Test that a business-logic failure from the fulfillment API retries setup."""
    mock_provider.enable.side_effect = PlaceFulfillmentError("not authorized")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
    "mock_provider",
)
async def test_setup_mqtt_connection_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that a rejected MQTT connection retries setup."""
    mock_mqtt_client.wait_for_connection.side_effect = PlaceMqttConnectionError(
        "MQTT connection rejected"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
    "mock_provider",
)
async def test_setup_mqtt_connection_failure_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Retry setup after the initial MQTT connection fails."""
    mock_mqtt_client.connect.side_effect = [
        PlaceMqttConnectionError("Failed to establish MQTT connection"),
        None,
    ]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_mqtt_client.loop_start.assert_not_called()
    mock_mqtt_client.wait_for_connection.assert_not_called()
    mock_mqtt_client.disconnect.assert_called_once()
    mock_mqtt_client.loop_stop.assert_called_once()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_mqtt_client.connect.call_count == 2
    mock_mqtt_client.loop_start.assert_called_once()
    mock_mqtt_client.wait_for_connection.assert_called_once()

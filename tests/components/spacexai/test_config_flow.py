"""Tests for the SpaceXAI config flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from spacexai_subscription_client import (
    Account,
    AuthenticationError,
    AuthorizationDeniedError,
    ConnectionFailureError,
    DeviceAuthorization,
    DeviceAuthorizationExpiredError,
    OAuthToken,
    PermissionDeniedError,
    RateLimitError,
    RequestTimeoutError,
    SpaceXAISubscriptionError,
)

from homeassistant.components.spacexai.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.httpx_client import get_async_client

from .conftest import ACCESS_TOKEN, REFRESH_TOKEN

from tests.common import MockConfigEntry

TOKEN_RESPONSE = {
    "access_token": ACCESS_TOKEN,
    "refresh_token": REFRESH_TOKEN,
    "expires_in": 3600,
    "token_type": "Bearer",
}
TOKEN_DATA = {**TOKEN_RESPONSE, "expires_at": 1234.0}
DEVICE_AUTHORIZATION = DeviceAuthorization(
    device_code="device-code",
    user_code="ABCD-1234",
    verification_uri="https://accounts.x.ai/oauth2/device",
    verification_uri_complete=(
        "https://accounts.x.ai/oauth2/device?user_code=ABCD-1234"
    ),
    expires_in=1800,
    interval=1,
    expires_at_monotonic=999999999.0,
)


async def _start_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Start a SpaceXAI user flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def _finish_device_progress(
    hass: HomeAssistant, mock_flow_client: MagicMock, result: ConfigFlowResult
) -> ConfigFlowResult:
    """Advance a device flow after its polling task completes."""
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["description_placeholders"] == {
        "user_code": "ABCD-1234",
        "verification_uri": "https://accounts.x.ai/oauth2/device?user_code=ABCD-1234",
    }
    mock_flow_client.poll_event.set()
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


async def _finish_conversation(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    model: str = "grok-4.6",
) -> None:
    """Create an entry and verify the saved account and conversation settings."""
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "conversation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: model,
            CONF_PROMPT: "Be concise.",
            CONF_LLM_HASS_API: [],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home User"
    assert result["result"].unique_id == "account-123"
    assert result["data"] == {
        "auth_implementation": DOMAIN,
        "token": TOKEN_DATA,
    }
    assert result["subentries"] == [
        {
            "subentry_type": "conversation",
            "title": "Grok",
            "unique_id": None,
            "data": {
                CONF_MODEL: model,
                CONF_PROMPT: "Be concise.",
            },
        }
    ]


def _set_successful_poll(mock_flow_client: MagicMock) -> None:
    """Make token polling wait until the progress form has been asserted."""
    mock_flow_client.poll_event = asyncio.Event()

    async def _async_poll(*_args: object) -> OAuthToken:
        await mock_flow_client.poll_event.wait()
        return OAuthToken(TOKEN_DATA)

    mock_flow_client.async_poll_device_token.side_effect = _async_poll


def _set_poll_error(
    mock_flow_client: MagicMock, error: type[SpaceXAISubscriptionError]
) -> None:
    """Make token polling fail after the progress form has been asserted."""
    mock_flow_client.poll_event = asyncio.Event()

    async def _async_poll(*_args: object) -> OAuthToken:
        await mock_flow_client.poll_event.wait()
        raise error

    mock_flow_client.async_poll_device_token.side_effect = _async_poll


@pytest.fixture
def mock_flow_client(mock_spacexai_subscription_client: MagicMock) -> MagicMock:
    """Return a successful mocked client for the config flow."""
    client = mock_spacexai_subscription_client
    client.async_request_device_authorization = AsyncMock(
        return_value=DEVICE_AUTHORIZATION
    )
    client.async_poll_device_token = AsyncMock()
    client.async_get_account = AsyncMock(
        return_value=Account("account-123", "Home User", "home@test")
    )
    client.async_list_models = AsyncMock(return_value=("grok-4.5", "grok-4.6"))
    _set_successful_poll(client)
    return client


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_oauth_flow(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Complete device login and create one Conversation subentry."""
    with patch(
        "homeassistant.components.spacexai.SpaceXAISubscriptionClient",
        return_value=mock_flow_client,
    ) as client_class:
        result = await _start_flow(hass)

    client_class.assert_called_once_with(
        async_get_clientsession(hass), get_async_client(hass)
    )
    result = await _finish_device_progress(hass, mock_flow_client, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "conversation"
    assert result["data_schema"].schema[CONF_MODEL].config["options"] == [
        "grok-4.5",
        "grok-4.6",
    ]

    await _finish_conversation(hass, result)
    mock_flow_client.async_poll_device_token.assert_awaited_once_with(
        DEVICE_AUTHORIZATION
    )
    mock_flow_client.async_get_account.assert_awaited_once_with(ACCESS_TOKEN)
    mock_flow_client.async_list_models.assert_awaited_once_with(ACCESS_TOKEN)


@pytest.mark.parametrize(
    ("assist_options", "expected_options"),
    [
        pytest.param(
            {},
            {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST]},
            id="default",
        ),
        pytest.param(
            {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST]},
            {CONF_LLM_HASS_API: [llm.LLM_API_ASSIST]},
            id="enabled",
        ),
        pytest.param({CONF_LLM_HASS_API: []}, {}, id="disabled"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_conversation_assist_options(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
    assist_options: dict[str, list[str]],
    expected_options: dict[str, list[str]],
) -> None:
    """Persist the default or selected Assist setting through the public flow."""
    result = await _finish_device_progress(
        hass, mock_flow_client, await _start_flow(hass)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "conversation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MODEL: "grok-4.6", **assist_options}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == "conversation"
    assert subentry.data == {CONF_MODEL: "grok-4.6", **expected_options}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_abort_during_device_polling(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Cancel pending device polling when the user closes the login flow."""
    poll_started = asyncio.Event()
    poll_cancelled = asyncio.Event()

    async def _async_poll(_authorization: DeviceAuthorization) -> OAuthToken:
        poll_started.set()
        try:
            await mock_flow_client.poll_event.wait()
        except asyncio.CancelledError:
            poll_cancelled.set()
            raise
        return OAuthToken(TOKEN_DATA)

    mock_flow_client.async_poll_device_token.side_effect = _async_poll
    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    async with asyncio.timeout(1):
        await poll_started.wait()

    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()

    assert poll_cancelled.is_set()
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not hass.config_entries.async_entries(DOMAIN)
    mock_flow_client.async_get_account.assert_not_awaited()
    mock_flow_client.async_list_models.assert_not_awaited()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_shutdown_during_device_polling(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cancel pending device polling before Home Assistant's final writes."""
    poll_started = asyncio.Event()
    cancellation_state: asyncio.Future[CoreState] = hass.loop.create_future()

    async def _async_poll(_authorization: DeviceAuthorization) -> OAuthToken:
        poll_started.set()
        try:
            await mock_flow_client.poll_event.wait()
        except asyncio.CancelledError:
            cancellation_state.set_result(hass.state)
            raise
        return OAuthToken(TOKEN_DATA)

    mock_flow_client.async_poll_device_token.side_effect = _async_poll
    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    async with asyncio.timeout(1):
        await poll_started.wait()

    await hass.async_stop()

    assert cancellation_state.result() is CoreState.stopping
    assert "was still running after final writes shutdown stage" not in caplog.text
    assert not hass.config_entries.async_entries(DOMAIN)
    mock_flow_client.async_get_account.assert_not_awaited()
    mock_flow_client.async_list_models.assert_not_awaited()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_device_authorization_rejected(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Abort when the OAuth client is rejected."""
    mock_flow_client.async_request_device_authorization.side_effect = (
        AuthenticationError
    )

    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_device_authorization_permission_denied(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Abort when the OAuth client is not permitted to start device login."""
    mock_flow_client.async_request_device_authorization.side_effect = (
        PermissionDeniedError
    )

    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_entitled"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_device_authorization_connection_error(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Retry when device authorization cannot be started."""
    mock_flow_client.async_request_device_authorization.side_effect = [
        SpaceXAISubscriptionError,
        DEVICE_AUTHORIZATION,
    ]

    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_connection_error"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    result = await _finish_device_progress(hass, mock_flow_client, result)
    await _finish_conversation(hass, result)
    assert mock_flow_client.async_request_device_authorization.await_count == 2


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ConnectionFailureError, id="connection"),
        pytest.param(RateLimitError, id="rate_limit"),
        pytest.param(RequestTimeoutError, id="timeout"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_device_authorization_transient_poll_error_and_retry(
    hass: HomeAssistant,
    error: type[SpaceXAISubscriptionError],
    mock_flow_client: MagicMock,
) -> None:
    """Retry transient polling failures with the same device authorization."""
    _set_poll_error(mock_flow_client, error)

    result = await _start_flow(hass)
    result = await _finish_device_progress(hass, mock_flow_client, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_connection_error"

    _set_successful_poll(mock_flow_client)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    result = await _finish_device_progress(hass, mock_flow_client, result)
    await _finish_conversation(hass, result)
    mock_flow_client.async_request_device_authorization.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "step_id"),
    [
        pytest.param(AuthorizationDeniedError, "device_denied", id="denied"),
        pytest.param(DeviceAuthorizationExpiredError, "device_timeout", id="expired"),
        pytest.param(SpaceXAISubscriptionError, "device_connection_error", id="other"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_device_authorization_terminal_poll_error_and_retry(
    hass: HomeAssistant,
    error: type[SpaceXAISubscriptionError],
    mock_flow_client: MagicMock,
    step_id: str,
) -> None:
    """Request a new device authorization after a terminal polling failure."""
    _set_poll_error(mock_flow_client, error)

    result = await _start_flow(hass)
    result = await _finish_device_progress(hass, mock_flow_client, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id

    _set_successful_poll(mock_flow_client)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    result = await _finish_device_progress(hass, mock_flow_client, result)
    await _finish_conversation(hass, result)
    assert mock_flow_client.async_request_device_authorization.await_count == 2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_device_authorization_poll_authentication_error(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Abort when device token polling rejects the OAuth client."""
    _set_poll_error(mock_flow_client, AuthenticationError)

    result = await _start_flow(hass)
    result = await _finish_device_progress(hass, mock_flow_client, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_device_authorization_poll_permission_denied(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Abort when the account cannot use the subscription token endpoint."""
    _set_poll_error(mock_flow_client, PermissionDeniedError)

    result = await _start_flow(hass)
    result = await _finish_device_progress(hass, mock_flow_client, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_entitled"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_account_validation_authentication_error(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Abort when the approved account rejects the access token."""
    mock_flow_client.async_get_account.side_effect = AuthenticationError

    result = await _finish_device_progress(
        hass, mock_flow_client, await _start_flow(hass)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_account_validation_permission_denied(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Abort when the approved account cannot use the subscription API."""
    mock_flow_client.async_list_models.side_effect = PermissionDeniedError

    result = await _finish_device_progress(
        hass, mock_flow_client, await _start_flow(hass)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_entitled"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_account_validation_connection_error_and_retry(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Retry account validation without repeating device authorization."""
    mock_flow_client.async_get_account.side_effect = SpaceXAISubscriptionError

    result = await _finish_device_progress(
        hass, mock_flow_client, await _start_flow(hass)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_validation_error"

    mock_flow_client.async_get_account.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    await _finish_conversation(hass, result)
    mock_flow_client.async_request_device_authorization.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_account_has_no_models(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
) -> None:
    """Retry validation when the approved account has no available models."""
    mock_flow_client.async_list_models.return_value = ()

    result = await _finish_device_progress(
        hass, mock_flow_client, await _start_flow(hass)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_validation_error"

    mock_flow_client.async_list_models.return_value = ("grok-4.5",)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    await _finish_conversation(hass, result, model="grok-4.5")
    mock_flow_client.async_request_device_authorization.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_client: MagicMock,
) -> None:
    """Abort when the signed-in account is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_flow(hass)
    result = await _finish_device_progress(hass, mock_flow_client, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_flow_client.async_list_models.assert_not_awaited()

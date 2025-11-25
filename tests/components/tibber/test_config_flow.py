"""Tests for Tibber config flow."""

import builtins
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientError
import pytest
from tibber import (
    FatalHttpExceptionError,
    InvalidLoginError,
    RetryableHttpExceptionError,
)

from homeassistant import config_entries
from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.application_credentials import TOKEN_URL
from homeassistant.components.tibber.config_flow import (
    DATA_API_DEFAULT_SCOPES,
    ERR_CLIENT,
    ERR_TIMEOUT,
    ERR_TOKEN,
)
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="tibber_setup", autouse=True)
def tibber_setup_fixture():
    """Patch tibber setup entry."""
    with patch("homeassistant.components.tibber.async_setup_entry", return_value=True):
        yield


def _mock_tibber(
    *,
    user_id: str = "unique_user_id",
    title: str = "title",
    update_side_effect: Exception | None = None,
) -> MagicMock:
    """Return a mocked Tibber GraphQL client."""
    tibber_mock = MagicMock()
    tibber_mock.user_id = user_id
    tibber_mock.name = title
    tibber_mock.update_info = AsyncMock()
    if update_side_effect is not None:
        tibber_mock.update_info.side_effect = update_side_effect
    return tibber_mock


async def test_show_config_form(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (builtins.TimeoutError(), ERR_TIMEOUT),
        (ClientError(), ERR_CLIENT),
        (InvalidLoginError(401), ERR_TOKEN),
        (RetryableHttpExceptionError(503), ERR_CLIENT),
        (FatalHttpExceptionError(404), ERR_CLIENT),
    ],
)
async def test_graphql_step_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Validate GraphQL errors are surfaced."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    tibber_mock = _mock_tibber(update_side_effect=exception)
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "invalid"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"][CONF_ACCESS_TOKEN] == expected_error


async def test_flow_entry_already_exists(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """GraphQL duplicates abort."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "old token"},
        unique_id="unique_user_id",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    tibber_mock = _mock_tibber()
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "new token"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_data_api_requires_credentials(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Abort when OAuth credentials are missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    tibber_mock = _mock_tibber()
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "valid"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_data_api_extra_authorize_scope(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Ensure the OAuth implementation requests Tibber scopes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    tibber_mock = _mock_tibber()
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "valid"}
        )

    handler = hass.config_entries.flow._progress[result["flow_id"]]
    assert handler.extra_authorize_data["scope"] == " ".join(DATA_API_DEFAULT_SCOPES)


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_full_flow_success(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test configuring Tibber via GraphQL + OAuth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    tibber_mock = _mock_tibber()
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "graphql-token"}
        )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    authorize_url = result["url"]
    state = parse_qs(urlparse(authorize_url).query)["state"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )

    data_api_client = MagicMock()
    data_api_client.get_userinfo = AsyncMock(
        return_value={"email": "mock-user@example.com"}
    )

    with patch(
        "homeassistant.components.tibber.config_flow.TibberDataAPI",
        return_value=data_api_client,
        create=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["data"]
    assert data[CONF_TOKEN]["access_token"] == "mock-access-token"
    assert data[CONF_ACCESS_TOKEN] == "graphql-token"
    assert data["auth_implementation"] == DOMAIN
    assert result["title"] == "mock-user@example.com"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_data_api_oauth_cannot_connect_abort(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Abort when OAuth succeeds but userinfo fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    tibber_mock = _mock_tibber()
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "graphql-token"}
        )

    authorize_url = result["url"]
    state = parse_qs(urlparse(authorize_url).query)["state"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )

    data_api_client = MagicMock()
    data_api_client.get_userinfo = AsyncMock(side_effect=ClientError("boom"))

    with patch(
        "homeassistant.components.tibber.config_flow.TibberDataAPI",
        return_value=data_api_client,
        create=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_data_api_abort_when_already_configured(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Ensure only a single Data API entry can be configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            CONF_TOKEN: {"access_token": "existing"},
            CONF_ACCESS_TOKEN: "stored-graphql",
        },
        unique_id="unique_user_id",
        title="Existing",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    tibber_mock = _mock_tibber()
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_graphql_reauth_updates_entry(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """GraphQL-only reauth simply updates the access token."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: "old-token",
        },
        unique_id="user-123",
        title="Old title",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": existing_entry.entry_id,
        },
        data=existing_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    tibber_mock = _mock_tibber(user_id="user-123", title="New title")
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    updated_entry = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated_entry
    assert updated_entry.data[CONF_ACCESS_TOKEN] == "new-token"
    assert updated_entry.title == "New title"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_data_api_reauth_updates_entry(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Data API reauth refreshes both GraphQL and OAuth tokens."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            CONF_TOKEN: {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
            },
            CONF_ACCESS_TOKEN: "old-graphql",
        },
        unique_id="old@example.com",
        title="old@example.com",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": existing_entry.entry_id,
        },
        data=existing_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    tibber_mock = _mock_tibber(user_id="old@example.com", title="old@example.com")
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "new-graphql"}
        )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    state = parse_qs(urlparse(result["url"]).query)["state"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )

    data_api_client = MagicMock()
    data_api_client.get_userinfo = AsyncMock(return_value={"email": "old@example.com"})

    with patch(
        "homeassistant.components.tibber.config_flow.TibberDataAPI",
        return_value=data_api_client,
        create=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    updated_entry = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated_entry
    assert updated_entry.data[CONF_ACCESS_TOKEN] == "new-graphql"
    assert updated_entry.data[CONF_TOKEN]["access_token"] == "new-access-token"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_data_api_reauth_wrong_account_abort(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Abort Data API reauth when Tibber reports another account."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            CONF_TOKEN: {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
            },
            CONF_ACCESS_TOKEN: "old-graphql",
        },
        unique_id="old@example.com",
        title="old@example.com",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": existing_entry.entry_id,
        },
        data=existing_entry.data,
    )

    tibber_mock = _mock_tibber(user_id="old@example.com", title="old@example.com")
    with patch("tibber.Tibber", return_value=tibber_mock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "new-graphql"}
        )

    state = parse_qs(urlparse(result["url"]).query)["state"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )

    data_api_client = MagicMock()
    data_api_client.get_userinfo = AsyncMock(
        return_value={"email": "other@example.com"}
    )

    with patch(
        "homeassistant.components.tibber.config_flow.TibberDataAPI",
        return_value=data_api_client,
        create=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert result["description_placeholders"] == {"email": "old@example.com"}

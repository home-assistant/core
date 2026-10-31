"""Test the A Better Routeplanner config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock

from aioabrp import AbrpApiError, AbrpAuthError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.abrp.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    USER_SUB,
    build_id_token,
    complete_oauth_callback,
)


@pytest.fixture
def use_cloud(hass: HomeAssistant) -> None:
    """Set up the cloud component."""
    hass.config.components.add("cloud")


def _mock_token_post(
    aioclient_mock: AiohttpClientMocker,
    id_token: str | None = build_id_token(),
    access_token: str = "mock-access-token",
    refresh_token: str | None = "mock-refresh-token",
) -> None:
    """Queue the standard token-exchange response on ``aioclient_mock``."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": id_token,
        },
    )


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_abrp_client")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Happy-path OAuth flow creates a config entry."""
    # Freeze time so the token ``expires_at`` is stable for the snapshot.
    freezer.move_to("2026-01-01 00:00:00+00:00")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&state={state}"
        "&scope=openid+profile+email+offline_access"
    )

    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USER_SUB
    assert result["result"].data == snapshot

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    _method, _url, data, _headers = aioclient_mock.mock_calls[0]
    assert data["client_id"] == CLIENT_ID
    assert data["client_secret"] == CLIENT_SECRET
    assert data["grant_type"] == "authorization_code"
    assert data["code"] == "abcd"


async def test_no_cloud(hass: HomeAssistant) -> None:
    """The flow aborts when the cloud integration is not set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cloud_not_enabled"


@pytest.mark.parametrize(
    ("id_token", "expected_title"),
    [
        pytest.param(
            build_id_token(name="Sofie"),
            "A Better Routeplanner (Sofie)",
            id="display_name",
        ),
        pytest.param(build_id_token(), "A Better Routeplanner", id="no_display_name"),
    ],
)
@pytest.mark.usefixtures(
    "current_request_with_host", "use_cloud", "mock_setup_entry", "mock_abrp_client"
)
async def test_entry_title(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    id_token: str,
    expected_title: str,
) -> None:
    """The entry title appends the account's display name when it has one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock, id_token)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == expected_title
    assert result["result"].unique_id == USER_SUB


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """A second flow for the same ``sub`` aborts with ``already_configured``."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    # The guard must short-circuit before any garage request.
    mock_abrp_client.assert_not_called()


@pytest.mark.parametrize(
    ("status", "expected_reason"),
    [
        pytest.param(HTTPStatus.BAD_REQUEST, "oauth_unauthorized", id="4xx"),
        pytest.param(HTTPStatus.INTERNAL_SERVER_ERROR, "oauth_failed", id="5xx"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_token_endpoint_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    expected_reason: str,
) -> None:
    """A non-200 response from the token endpoint aborts the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(OAUTH2_TOKEN, status=status)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_no_vehicles_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
) -> None:
    """An account with an empty garage aborts the flow."""
    mock_abrp_client.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_vehicles"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


@pytest.mark.parametrize(
    ("id_token", "refresh_token"),
    [
        pytest.param(None, "mock-refresh-token", id="missing_id_token"),
        pytest.param(
            "header.not-base64!.sig", "mock-refresh-token", id="unparsable_id_token"
        ),
        pytest.param(build_id_token(), None, id="missing_refresh_token"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_initial_add_unusable_token_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    id_token: str | None,
    refresh_token: str | None,
) -> None:
    """An unusable id_token or a missing refresh_token aborts the initial add."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock, id_token, refresh_token=refresh_token)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        pytest.param(
            AbrpAuthError("invalid session"),
            "api_unauthorized",
            id="auth_error",
        ),
        pytest.param(
            AbrpApiError("backend overloaded"),
            "cannot_connect",
            id="api_error",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_garage_fetch_error_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
    side_effect: Exception,
    expected_reason: str,
) -> None:
    """An API error during the garage fetch aborts the flow."""
    mock_abrp_client.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

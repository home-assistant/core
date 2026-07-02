"""Test the A Better Routeplanner config flow."""

import base64
import hashlib
from http import HTTPStatus
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from aioabrp import AbrpApiError, AbrpAuthError, AbrpVehicle
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.abetterrouteplanner.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_CLIENT_ID,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    REDIRECT_URI,
    USER_SUB,
    build_id_token,
    complete_oauth_callback,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

EXPECTED_SCOPE = "oidc profile email offline_access"


def _vehicle(vehicle_id: int, name: str) -> AbrpVehicle:
    """Build a typed ``AbrpVehicle`` for a config-flow garage."""
    return AbrpVehicle(
        vehicle_id=vehicle_id,
        name=name,
        vehicle_model=f"model:{vehicle_id}",
        paint=None,
    )


def _mock_token_post(aioclient_mock: AiohttpClientMocker) -> None:
    """Queue the standard token-exchange response on ``aioclient_mock``."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": build_id_token(USER_SUB),
        },
    )


@pytest.fixture(autouse=True)
async def setup_auth(hass: HomeAssistant) -> None:
    """Set up the auth component so /auth/external/callback is registered.

    The integration's own component is intentionally NOT loaded here so the
    tests mirror the UI behaviour: opening the config flow from the
    "Add integration" dialog does not call ``async_setup`` first. The flow
    handler is responsible for ensuring the OAuth2 implementation is
    registered before the flow proceeds.
    """
    assert await async_setup_component(hass, "auth", {})


def _compute_expected_challenge(verifier: str) -> str:
    """Recompute the PKCE S256 challenge from a verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Happy-path OAuth flow + picker creates a config entry with PKCE + vehicle_ids."""
    # Freeze time so the token ``expires_at`` is stable for the snapshot.
    freezer.move_to("2026-01-01 00:00:00+00:00")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"

    parsed_url = urlparse(result["url"])
    assert f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" == (
        OAUTH2_AUTHORIZE
    )

    parsed_query = parse_qs(parsed_url.query)
    assert parsed_query["response_type"] == ["code"]
    assert parsed_query["client_id"] == [OAUTH2_CLIENT_ID]
    assert parsed_query["redirect_uri"] == [REDIRECT_URI]
    assert parsed_query["scope"] == [EXPECTED_SCOPE]
    assert parsed_query["code_challenge_method"] == ["S256"]
    code_challenge = parsed_query["code_challenge"][0]
    assert code_challenge
    assert "client_secret" not in parsed_query

    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    _mock_token_post(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": [str(MOCK_VEHICLE_ID)]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USER_SUB
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["vehicle_ids"] == [str(MOCK_VEHICLE_ID)]
    assert result["result"].data == snapshot

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    # First aioclient call is the OAuth token exchange; verify PKCE round-trip.
    _method, _url, data, _headers = aioclient_mock.mock_calls[0]
    assert "client_secret" not in data
    assert data["grant_type"] == "authorization_code"
    assert data["code"] == "abcd"
    code_verifier = data["code_verifier"]
    assert isinstance(code_verifier, str)
    assert code_verifier
    # Round-trip: challenge published in authorize URL matches verifier sent
    # to the token endpoint.
    assert _compute_expected_challenge(code_verifier) == code_challenge


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """A second flow for the same ``sub`` aborts with ``already_configured``."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": build_id_token(USER_SUB),
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("status", "expected_reason"),
    [
        pytest.param(HTTPStatus.BAD_REQUEST, "oauth_unauthorized", id="4xx"),
        pytest.param(HTTPStatus.INTERNAL_SERVER_ERROR, "oauth_failed", id="5xx"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
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


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_pick_vehicles_no_vehicles_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
) -> None:
    """An empty garage aborts the flow with ``no_vehicles``."""
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
    ("vehicle_ids", "picked_ids"),
    [
        pytest.param([1001], ["1001"], id="single_picked"),
        pytest.param([1001, 1002, 1003], ["1001", "1003"], id="multi_subset_picked"),
        pytest.param(
            [1001, 1002, 1003],
            ["1001", "1002", "1003"],
            id="multi_all_picked",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_pick_vehicles_creates_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
    vehicle_ids: list[int],
    picked_ids: list[str],
) -> None:
    """Picker shows for 1/N vehicles; selected ids land in entry.data['vehicle_ids']."""
    mock_abrp_client.return_value = [
        _vehicle(vid, f"Vehicle {vid}") for vid in vehicle_ids
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": picked_ids}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data["vehicle_ids"] == picked_ids
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    "id_token",
    [
        pytest.param(None, id="missing"),
        pytest.param("header.not-base64!.sig", id="unparsable"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_initial_add_unusable_id_token_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    id_token: str | None,
) -> None:
    """An absent or unparsable id_token aborts the initial add (finding D).

    The flow owns two guards: a missing ``id_token`` and an ``AbrpAuthError``
    raised by ``parse_unverified_identity``. Enumerating the malformed-payload
    shapes that raise that error is the library's concern, not the integration's.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": id_token,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_pick_vehicles_aborts_if_entry_appeared_during_picker(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Picker submission re-runs the duplicate check (finding F race coverage).

    If a parallel flow lands an entry with the same ``sub`` while the user is
    still on the picker form, submitting the picker must abort with
    ``already_configured`` rather than creating a second entry.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    # Simulate a parallel flow that completed and landed an entry with the
    # same unique_id between picker render and picker submission.
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": [str(MOCK_VEHICLE_ID)]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Only the racing entry remains; no second entry was created.
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_pick_vehicles_empty_selection_rejected(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
) -> None:
    """An empty picker submission re-renders the form with a ``base`` error.

    Validation lives in the step body (not the schema): the developer found
    that ``vol.Length(min=1)`` at the schema layer raises ``vol.Invalid`` →
    ``data_entry_flow.InvalidData`` rather than re-rendering the form, so the
    flow handler returns ``async_show_form(errors={"base": ...})`` itself.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": []}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"
    assert result.get("errors") == {"base": "select_at_least_one"}
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
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_garage_fetch_error_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
    side_effect: Exception,
    expected_reason: str,
) -> None:
    """An API error between OAuth and the picker aborts the flow.

    ``AbrpAuthError`` maps to ``api_unauthorized`` and ``AbrpApiError`` maps to
    ``cannot_connect``.
    """
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

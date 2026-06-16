"""Test the A Better Routeplanner config flow."""

import base64
import hashlib
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from aioabrp import AbrpApiError, AbrpAuthError, AbrpVehicle
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.abetterrouteplanner.const import (
    CONF_VEHICLE_IDS,
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


def _id_token_with_raw_payload(payload_json: bytes) -> str:
    """Build a ``header.payload.signature`` id_token from raw payload bytes.

    Unlike :func:`build_id_token` (which assumes the payload is a dict with a
    ``sub`` claim), this helper takes the raw payload as bytes so tests can
    exercise non-dict / malformed-shape branches in ``_decode_jwt_sub``.
    """
    payload_b64 = base64.urlsafe_b64encode(payload_json).rstrip(b"=").decode()
    return f"header.{payload_b64}.sig"


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
    ("returned_sub", "expected_reason", "expected_access_token"),
    [
        pytest.param(
            USER_SUB,
            "reauth_successful",
            "updated-access-token",
            id="reauth_successful",
        ),
        pytest.param(
            "other-user",
            "wrong_account",
            "mock-access-token",
            id="wrong_account",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    returned_sub: str,
    expected_reason: str,
    expected_access_token: str,
) -> None:
    """Reauth updates an existing entry or aborts on account mismatch."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": build_id_token(returned_sub),
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.unique_id == USER_SUB
    assert config_entry.data["token"]["access_token"] == expected_access_token


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
        pytest.param("", id="empty"),
        pytest.param("opaque", id="opaque_single_segment"),
        pytest.param("header.not-base64!.sig", id="bad_base64"),
        pytest.param("header..sig", id="empty_payload"),
        pytest.param(_id_token_with_raw_payload(b"[1,2,3]"), id="payload_is_list"),
        pytest.param(
            _id_token_with_raw_payload(b'"justastring"'),
            id="payload_is_scalar",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_initial_add_malformed_id_token_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    id_token: str,
) -> None:
    """Malformed id_token on the initial add aborts cleanly (finding D)."""
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


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_skips_pick_vehicles(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_abrp_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """A reauth flow must complete without driving the picker (no garage fetch)."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": build_id_token(USER_SUB),
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["token"]["access_token"] == "updated-access-token"

    # The garage must not be fetched during reauth (would imply the picker
    # step ran).
    assert mock_abrp_client.call_count == 0


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_preserves_vehicle_ids(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Reauth must merge token data rather than replacing ``entry.data`` wholesale.

    Regression guard: a prior implementation used
    ``async_update_reload_and_abort(entry, data=data)`` which wipes
    ``entry.data`` (including ``vehicle_ids``); the fix is ``data_updates=data``.
    """
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, "vehicle_ids": ["1001", "1002"]},
    )

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": build_id_token(USER_SUB),
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["token"]["access_token"] == "updated-access-token"
    assert config_entry.data["vehicle_ids"] == ["1001", "1002"]


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_without_id_token_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Reauth aborts ``oauth_error`` when the refresh response omits ``id_token``.

    Regression guard for finding A (round 2): the previous "trust the stored
    unique_id when id_token is missing" behaviour was a security hole — a
    different browser-account's refresh would silently overwrite the entry.
    We now require a verifiable ``sub`` claim on every reauth.
    """
    config_entry.add_to_hass(hass)
    original_token = dict(config_entry.data["token"])

    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            # id_token deliberately omitted.
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
    # Stored token must NOT have been rewritten — the entry is untouched.
    assert config_entry.unique_id == USER_SUB
    assert config_entry.data["token"] == original_token


# Reauth ``login_hint`` prefill --------------------------------------------
#
# The flow handler must attach ``login_hint=<email>`` to the OAuth authorize
# URL on a reauth flow so the IdP can pre-fill the email field. The email is
# sourced from the stored ``id_token`` (OIDC ``email`` claim). All adversarial
# paths — malformed token, missing claim, non-string claim — degrade
# gracefully to "no prefill" rather than blocking reauth.


# Sentinels so the parametrize table can encode "token dict missing entirely"
# and "id_token key missing from token dict" without branching inside the test
# body. Per CLAUDE.md (no branching in tests) the dispatch lives in the helper.
_NO_TOKEN_KEY = object()
_NO_ID_TOKEN_KEY = object()


def _build_reauth_entry_data(
    id_token_field: object,
    token_entry: dict[str, Any],
) -> dict[str, Any]:
    """Build ``entry.data`` exercising one branch of the login_hint guards.

    ``id_token_field`` is either a sentinel signalling structural absence
    (``_NO_TOKEN_KEY`` / ``_NO_ID_TOKEN_KEY``) or a string to splice into
    ``entry.data["token"]["id_token"]``. The dispatch lives here so the
    parametrized test body has a single linear path.
    """
    if id_token_field is _NO_TOKEN_KEY:
        return {"auth_implementation": DOMAIN, CONF_VEHICLE_IDS: []}
    if id_token_field is _NO_ID_TOKEN_KEY:
        token_without_id = {k: v for k, v in token_entry.items() if k != "id_token"}
        return {
            "auth_implementation": DOMAIN,
            "token": token_without_id,
            CONF_VEHICLE_IDS: [],
        }
    return {
        "auth_implementation": DOMAIN,
        "token": {**token_entry, "id_token": id_token_field},
        CONF_VEHICLE_IDS: [],
    }


async def _drive_reauth_to_authorize_url(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> dict[str, Any]:
    """Drive a reauth flow to the EXTERNAL_STEP authorize URL.

    Shared by all login_hint tests: ``add_to_hass`` the entry, start the
    reauth flow, walk past the ``reauth_confirm`` form, and return the
    EXTERNAL_STEP result whose ``url`` is the authorize URL under test.
    """
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    return result


@pytest.mark.parametrize(
    "email",
    [
        pytest.param("user@example.invalid", id="plain"),
        pytest.param("user+tag@example.invalid", id="email_with_plus"),
        pytest.param("user.name@example.invalid", id="email_with_dot"),
        pytest.param("USER@EXAMPLE.INVALID", id="email_uppercase"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_authorize_url_includes_login_hint(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    email: str,
) -> None:
    """Reauth attaches ``login_hint=<email>`` from the stored id_token.

    Parametrized over four happy-path email shapes that exercise the
    URL-encoding round-trip: ``+`` (reserved), ``.`` (unreserved), and a
    pure-uppercase variant. ``parse_qs`` percent-decodes the value back, so
    after the round-trip we must recover the original email verbatim.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_SUB,
        data=_build_reauth_entry_data(
            build_id_token(USER_SUB, email=email), token_entry
        ),
    )

    result = await _drive_reauth_to_authorize_url(hass, config_entry)

    parsed_query = parse_qs(urlparse(result["url"]).query)
    assert parsed_query["login_hint"] == [email]


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_initial_add_authorize_url_omits_login_hint(
    hass: HomeAssistant,
) -> None:
    """Initial-add flow must NOT attach ``login_hint``.

    Negation-then-trigger oracle pin: without this, a future regression that
    defaults ``login_hint`` to a hard-coded value (or always-on regardless of
    flow source) would silently pass the positive reauth test. The initial-add
    flow has no entry yet → no email known to HA → omit the hint.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    parsed_query = parse_qs(urlparse(result["url"]).query)
    assert "login_hint" not in parsed_query


@pytest.mark.parametrize(
    "id_token_field",
    [
        pytest.param(_NO_TOKEN_KEY, id="token_dict_missing"),
        pytest.param(_NO_ID_TOKEN_KEY, id="id_token_key_missing"),
        pytest.param("header.not-base64!.sig", id="jwt_bad_base64"),
        pytest.param(build_id_token(USER_SUB), id="email_claim_missing"),
        pytest.param(
            _id_token_with_raw_payload(b'{"sub":"x","email":""}'),
            id="email_claim_empty_string",
        ),
        pytest.param(
            _id_token_with_raw_payload(b'{"sub":"x","email":42}'),
            id="email_claim_non_string",
        ),
        pytest.param(
            _id_token_with_raw_payload(b"[1,2,3]"),
            id="payload_is_list",
        ),
        pytest.param(
            _id_token_with_raw_payload(b'"justastring"'),
            id="payload_is_scalar",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_authorize_url_omits_login_hint_on_bad_id_token(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    id_token_field: object,
) -> None:
    """Reauth omits ``login_hint`` for every adversarial id_token shape.

    Each parametrize case exercises a distinct guard in the flow handler:
    missing ``token`` dict, missing ``id_token`` key, malformed JWT (one of
    the in-band exceptions surfaced by the unverified-JWT decode helper),
    no ``email`` claim, empty-string ``email``, non-string ``email``, and
    structurally-decodable-but-non-dict payloads (list, scalar) where
    ``payload.get("email")`` would raise ``AttributeError``. All converge on
    "omit the hint" so reauth proceeds without prefill.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_SUB,
        data=_build_reauth_entry_data(id_token_field, token_entry),
    )

    result = await _drive_reauth_to_authorize_url(hass, config_entry)

    parsed_query = parse_qs(urlparse(result["url"]).query)
    assert "login_hint" not in parsed_query


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_authorize_url_preserves_framework_query_keys(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
) -> None:
    """Adding ``login_hint`` must not trample framework-supplied query keys.

    Order-independence pin: the framework merges the flow handler's
    ``extra_authorize_data`` on top of the implementation's, so all the
    pre-existing OAuth query keys (``response_type``, ``client_id``,
    ``redirect_uri``, ``scope``, ``state``, ``code_challenge``,
    ``code_challenge_method``) must survive the merge intact alongside the new
    ``login_hint`` we contribute.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_SUB,
        data=_build_reauth_entry_data(
            build_id_token(USER_SUB, email="user@example.invalid"), token_entry
        ),
    )

    result = await _drive_reauth_to_authorize_url(hass, config_entry)

    parsed_query = parse_qs(urlparse(result["url"]).query)
    assert set(parsed_query) >= {
        "response_type",
        "client_id",
        "redirect_uri",
        "scope",
        "state",
        "code_challenge",
        "code_challenge_method",
        "login_hint",
    }
    assert parsed_query["login_hint"] == ["user@example.invalid"]
    assert parsed_query["client_id"] == [OAUTH2_CLIENT_ID]
    assert parsed_query["redirect_uri"] == [REDIRECT_URI]
    assert parsed_query["scope"] == [EXPECTED_SCOPE]
    assert parsed_query["code_challenge_method"] == ["S256"]

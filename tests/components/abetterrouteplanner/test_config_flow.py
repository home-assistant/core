"""Test the A Better Routeplanner config flow."""

import base64
import hashlib
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

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
    ABRP_GET_TLM_URL,
    MOCK_VEHICLE_ID,
    REDIRECT_URI,
    USER_SUB,
    build_garage_response,
    build_id_token,
    build_vehicle_record,
    complete_oauth_callback,
)

from tests.common import MockConfigEntry, get_schema_suggested_value
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

EXPECTED_SCOPE = "oidc profile email offline_access"


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
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response())

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
) -> None:
    """An empty garage aborts the flow with ``no_vehicles``."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response([]))

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
    vehicle_ids: list[int],
    picked_ids: list[str],
) -> None:
    """Picker shows for 1/N vehicles; selected ids land in entry.data['vehicle_ids']."""
    records = [
        build_vehicle_record(vehicle_id=vid, name=f"Vehicle {vid}")
        for vid in vehicle_ids
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response(records))

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
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response())

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
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response())

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
    ("api_response_kwargs", "expected_reason"),
    [
        pytest.param(
            {"json": {"status": "error", "error": "invalid session"}},
            "api_unauthorized",
            id="auth_error_envelope",
        ),
        pytest.param(
            {"json": {"status": "error", "error": "backend overloaded"}},
            "cannot_connect",
            id="generic_error_envelope",
        ),
        pytest.param(
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR},
            "cannot_connect",
            id="server_error",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_garage_fetch_error_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    api_response_kwargs: dict[str, Any],
    expected_reason: str,
) -> None:
    """An API error between OAuth and the picker aborts the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _mock_token_post(aioclient_mock)
    aioclient_mock.post(ABRP_GET_TLM_URL, **api_response_kwargs)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_skips_pick_vehicles(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """A reauth flow must complete without driving the picker (no get_tlm call)."""
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

    # Only the OAuth token endpoint was called; the garage endpoint must not
    # be hit during reauth (would imply the picker step ran).
    called_urls = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert ABRP_GET_TLM_URL not in called_urls


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


async def _drive_reconfigure_through_token_exchange(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    *,
    returned_sub: str = USER_SUB,
) -> dict[str, Any]:
    """Drive a reconfigure flow up to (but not including) the garage fetch.

    Starts the reconfigure flow, walks the OAuth external callback, and queues
    a token-exchange response with ``returned_sub`` baked into the ``id_token``.
    Returns the in-progress flow's last result (after the configure call that
    triggers the token exchange).
    """
    result = await config_entry.start_reconfigure_flow(hass)
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

    return await hass.config_entries.flow.async_configure(result["flow_id"])


def _reconfigure_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Build the canonical config entry used by reconfigure tests.

    The entry's ``unique_id`` matches :data:`USER_SUB` (the default ``sub``
    returned by :func:`build_id_token`) so the re-OAuth round-trip lands on
    the same account on the happy path. ``vehicle_ids=["1"]`` is the
    canonical starting selection.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            "vehicle_ids": ["1"],
        },
    )


@pytest.mark.parametrize(
    ("picked_ids", "expected_vehicle_ids"),
    [
        pytest.param(["2"], ["2"], id="happy_path_change_selection"),
        pytest.param(["1"], ["1"], id="happy_path_select_same"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reconfigure_happy_path(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, Any],
    picked_ids: list[str],
    expected_vehicle_ids: list[str],
) -> None:
    """Reconfigure updates ``vehicle_ids`` and refreshes the stored token."""
    config_entry = _reconfigure_entry(token_entry)
    config_entry.add_to_hass(hass)

    records = [
        build_vehicle_record(vehicle_id=1, name="Vehicle 1"),
        build_vehicle_record(vehicle_id=2, name="Vehicle 2"),
    ]
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response(records))

    result = await _drive_reconfigure_through_token_exchange(
        hass, hass_client_no_auth, aioclient_mock, config_entry
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": picked_ids}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.unique_id == USER_SUB
    assert config_entry.data["vehicle_ids"] == expected_vehicle_ids
    assert config_entry.data["token"]["access_token"] == "updated-access-token"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reconfigure_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, Any],
) -> None:
    """Re-OAuth with a different ``sub`` aborts with ``wrong_account``.

    The garage fetch must NOT happen on the wrong-account path — the
    unique-id guard runs first.
    """
    config_entry = _reconfigure_entry(token_entry)
    config_entry.add_to_hass(hass)
    original_data = dict(config_entry.data)

    result = await _drive_reconfigure_through_token_exchange(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        config_entry,
        returned_sub="someone-else",
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert config_entry.unique_id == USER_SUB
    assert config_entry.data == original_data

    called_urls = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert ABRP_GET_TLM_URL not in called_urls


@pytest.mark.parametrize(
    ("api_response_kwargs", "expected_reason"),
    [
        pytest.param(
            {"json": {"status": "error", "error": "invalid session"}},
            "api_unauthorized",
            id="api_unauthorized",
        ),
        pytest.param(
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR},
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            {"json": build_garage_response([])},
            "no_vehicles",
            id="no_vehicles",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reconfigure_garage_fetch_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, Any],
    api_response_kwargs: dict[str, Any],
    expected_reason: str,
) -> None:
    """Garage-fetch failure on reconfigure aborts with the matching reason."""
    config_entry = _reconfigure_entry(token_entry)
    config_entry.add_to_hass(hass)
    original_data = dict(config_entry.data)

    aioclient_mock.post(ABRP_GET_TLM_URL, **api_response_kwargs)

    result = await _drive_reconfigure_through_token_exchange(
        hass, hass_client_no_auth, aioclient_mock, config_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert config_entry.data == original_data


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reconfigure_empty_submission(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, Any],
) -> None:
    """Submitting an empty selection on reconfigure re-renders with an error."""
    config_entry = _reconfigure_entry(token_entry)
    config_entry.add_to_hass(hass)

    records = [
        build_vehicle_record(vehicle_id=1, name="Vehicle 1"),
        build_vehicle_record(vehicle_id=2, name="Vehicle 2"),
    ]
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response(records))

    result = await _drive_reconfigure_through_token_exchange(
        hass, hass_client_no_auth, aioclient_mock, config_entry
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": []}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"
    assert result.get("errors") == {"base": "select_at_least_one"}
    assert config_entry.data["vehicle_ids"] == ["1"]


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reconfigure_picker_defaults_to_current_selection(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """First picker render on reconfigure preselects ``entry.data['vehicle_ids']``.

    Initial-add defaults to "all vehicles"; reconfigure must default to the
    current selection so the user's existing choice isn't silently replaced
    by the all-set on cancel/back. The schema's ``suggested_values`` is also
    snapshotted to catch any future drift.
    """
    config_entry = _reconfigure_entry(token_entry)
    config_entry.add_to_hass(hass)

    records = [
        build_vehicle_record(vehicle_id=1, name="Vehicle 1"),
        build_vehicle_record(vehicle_id=2, name="Vehicle 2"),
    ]
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response(records))

    result = await _drive_reconfigure_through_token_exchange(
        hass, hass_client_no_auth, aioclient_mock, config_entry
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, "vehicle_ids") == ["1"]
    assert result["data_schema"].schema == snapshot


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reconfigure_unions_prior_known_with_current_garage(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, Any],
) -> None:
    """Reconfigure unions prior ``CONF_KNOWN_VEHICLE_IDS`` with the current garage.

    A vehicle the user previously declined
    (present in ``KNOWN`` but not ``VEHICLE_IDS``) must remain in ``KNOWN`` after
    a reconfigure even if it is transiently absent from the garage at
    reconfigure-fetch time (deleted-and-re-added in ABRP, rate-limited poll,
    etc.). Naively overwriting ``KNOWN`` with ``{v.vehicle_id for v in
    self._vehicles}`` would drop the declined vehicle from the decline
    history; when it reappears later, the auto-add listener would treat it as
    "new" and onboard it, defeating the spouse-vehicle / rental-vehicle escape hatch.

    The union semantic — ``prior_known | {current_garage}`` — preserves the
    full decline history across transient garage flakes.

    Sequence:
    1. Entry exists with ``VEHICLE_IDS=["1"]`` and ``KNOWN=["1", "2"]`` (vehicle
       id ``2`` was declined in a previous reconfigure).
    2. Reconfigure flow starts. Garage at reconfigure-fetch time returns ONLY
       vehicle ``1`` (vehicle ``2`` is transiently absent).
    3. User submits ``VEHICLE_IDS=["1"]`` (no selection change).
    4. Assert post-flow: ``KNOWN`` contains BOTH ``"1"`` AND ``"2"`` — the
       prior decline of vehicle ``2`` is preserved.

    The downstream "listener leaves vehicle 2 alone when it reappears" is
    covered transitively by
    ``test_dynamic_devices.test_user_declined_vehicle_does_not_re_add`` —
    once KNOWN contains the declined id, the auto-add listener's
    ``new = present - known`` set-arithmetic guarantees no re-onboarding.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            "vehicle_ids": ["1"],
            "known_vehicle_ids": ["1", "2"],
        },
    )
    config_entry.add_to_hass(hass)

    # Garage at reconfigure time returns ONLY vehicle 1 — vehicle 2 is
    # transiently absent (deleted-and-re-added in ABRP, rate-limited poll,
    # etc.). The union semantic must keep "2" in KNOWN regardless.
    records = [build_vehicle_record(vehicle_id=1, name="Vehicle 1")]
    aioclient_mock.post(ABRP_GET_TLM_URL, json=build_garage_response(records))

    result = await _drive_reconfigure_through_token_exchange(
        hass, hass_client_no_auth, aioclient_mock, config_entry
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": ["1"]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["vehicle_ids"] == ["1"]
    # Union semantic: prior KNOWN U current garage = {"1", "2"} U {"1"} = {"1", "2"}.
    assert sorted(config_entry.data["known_vehicle_ids"]) == ["1", "2"]


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

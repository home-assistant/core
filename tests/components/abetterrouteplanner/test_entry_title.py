"""Tests for config-entry title scoping by authenticated account.

The initial-add path titles the entry per a JWT-claims preference chain:
``name`` (non-empty string) → ``email`` (non-empty string) → bare
``self.flow_impl.name``. The empty-string fall-through case is the
explicit empty-name guard.

Reauth and reconfigure paths must NEVER clobber a user-renamed entry's
title — the "don't clobber" semantic preserves user overrides.
"""

import base64
import json
from typing import Any

import pytest

from homeassistant.components.abetterrouteplanner.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import MOCK_VEHICLE_ID, USER_SUB, complete_oauth_callback

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def setup_auth(hass: HomeAssistant) -> None:
    """Set up the auth component so /auth/external/callback is registered.

    Mirrors the ``setup_auth`` autouse fixture in ``test_config_flow.py``:
    the integration's own component is intentionally NOT loaded so the
    config-flow exercises the lazy-impl-registration path that happens when
    the user opens "Add integration" without an existing entry.
    """
    assert await async_setup_component(hass, "auth", {})


def _build_id_token_with_payload(payload: dict[str, Any]) -> str:
    """Build a ``header.payload.signature`` id_token from a payload dict.

    The integration only inspects the payload (the OAuth code exchange already
    authenticated the issuer over TLS), so the header and signature are opaque
    placeholders.  Tests use this to drive the JWT-claims preference chain.

    ``conftest.build_id_token`` only supports ``sub`` + optional ``email``,
    but these tests need to inject a ``name`` claim too, so the payload is
    built inline here (the conftest contract explicitly allows building the
    token inline in the test for ``name``-claim cases).
    """
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"header.{payload_b64}.signature"


def _queue_token_post(aioclient_mock: AiohttpClientMocker, id_token: str) -> None:
    """Queue the standard token-exchange response with the given ``id_token``."""
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


# ---------------------------------------------------------------------------
# Parametrized cases — display-name preference chain on initial-add
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected_title"),
    [
        pytest.param(
            {"sub": USER_SUB, "name": "Sofie", "email": "s@e.com"},
            "A Better Routeplanner (Sofie)",
            id="name_claim_present",
        ),
        pytest.param(
            {"sub": USER_SUB, "email": "s@e.com"},
            "A Better Routeplanner (s@e.com)",
            id="name_missing_falls_back_to_email",
        ),
        pytest.param(
            {"sub": USER_SUB},
            "A Better Routeplanner",
            id="no_display_name_uses_bare_title",
        ),
        pytest.param(
            {"sub": USER_SUB, "name": "", "email": "user@example.com"},
            "A Better Routeplanner (user@example.com)",
            id="empty_name_falls_through_to_email",
        ),
    ],
)
@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "mock_abrp_client"
)
async def test_entry_title_from_claims(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    payload: dict[str, Any],
    expected_title: str,
) -> None:
    """Initial-add path titles the entry per the JWT-claims preference chain.

    Preference order: ``name`` (non-empty string) → ``email`` (non-empty
    string) → bare ``self.flow_impl.name``. The bare-title branch is the
    documented fallback when neither claim is present.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _queue_token_post(aioclient_mock, _build_id_token_with_payload(payload))

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": [str(MOCK_VEHICLE_ID)]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == expected_title


# ---------------------------------------------------------------------------
# Malformed JWT aborts on the strict-sub path (no fallback title)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_malformed_jwt_aborts_oauth_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A malformed id_token aborts with ``oauth_error`` — never a fallback title.

    The display-name extraction is asymmetric with ``sub`` extraction: the
    ``name`` / ``email`` chain returns ``None`` on any missing-or-malformed
    claim AND the title falls back to the bare impl name, but ``sub``
    extraction is strict — a JWT that can't be parsed never reaches the title
    code path because the flow aborts with ``oauth_error`` first.

    Regression guard against moving the exception band — any future
    refactor must not accidentally promote malformed-JWT to "ok with
    fallback title".
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _queue_token_post(aioclient_mock, "header.not-base64!.sig")

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


# ---------------------------------------------------------------------------
# Reauth must not clobber a user-renamed entry's title
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_does_not_retitle_existing_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Reauth completes successfully without rewriting ``entry.title``.

    Mirrors the ``device.name_by_user`` guard: an integration-side
    rename must NEVER overwrite a user override.  The entry's title is
    initialised to ``"My ABRP"`` (a user rename) and the reauth issues a
    fresh id_token with ``name="Different Name"`` — the completed reauth
    must leave ``entry.title`` exactly as the user set it.

    ``async_oauth_create_entry`` -> reauth branch goes through
    ``async_update_reload_and_abort(..., data_updates=data)`` which
    never touches ``title``. If a future patch adds
    ``async_update_entry(title=...)`` on the reauth path, this test
    fails loudly.
    """
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, title="My ABRP")
    assert config_entry.title == "My ABRP"

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])

    _queue_token_post(
        aioclient_mock,
        _build_id_token_with_payload(
            {"sub": USER_SUB, "name": "Different Name", "email": "diff@e.com"}
        ),
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.title == "My ABRP"


# ---------------------------------------------------------------------------
# Reconfigure must not clobber a user-renamed entry's title
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "mock_abrp_client"
)
async def test_reconfigure_does_not_retitle_existing_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, Any],
) -> None:
    """Reconfigure completes successfully without rewriting ``entry.title``.

    Same semantic as the reauth test above, exercising the reconfigure path
    which DOES walk the picker and finishes via
    ``async_update_reload_and_abort(..., data_updates=...)`` from inside
    ``async_step_pick_vehicles``.  That call also never touches ``title``,
    so the user's ``"My ABRP"`` rename survives across reconfigure even when
    the freshly-issued id_token carries a different ``name`` claim.

    Any accidental retitling on the reconfigure submission would fail
    this test.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USER_SUB,
        title="My ABRP",
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            "vehicle_ids": [str(MOCK_VEHICLE_ID)],
        },
    )
    config_entry.add_to_hass(hass)
    assert config_entry.title == "My ABRP"

    result = await config_entry.start_reconfigure_flow(hass)
    await complete_oauth_callback(hass, hass_client_no_auth, result["flow_id"])
    _queue_token_post(
        aioclient_mock,
        _build_id_token_with_payload(
            {"sub": USER_SUB, "name": "Different Name", "email": "diff@e.com"}
        ),
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_vehicles"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"vehicle_ids": [str(MOCK_VEHICLE_ID)]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.title == "My ABRP"

"""Tests for config-entry title construction on the initial-add path.

The flow appends ``identity.display_name`` to ``self.flow_impl.name`` when the
library resolves one, falling back to the bare implementation name otherwise.
Deriving the display name from the OIDC claims is the library's concern
(``aioabrp.parse_unverified_identity``); these tests only cover the title wiring.
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
    placeholders.

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


@pytest.mark.parametrize(
    ("payload", "expected_title"),
    [
        pytest.param(
            {"sub": USER_SUB, "name": "Sofie"},
            "A Better Routeplanner (Sofie)",
            id="display_name_present",
        ),
        pytest.param(
            {"sub": USER_SUB},
            "A Better Routeplanner",
            id="no_display_name_uses_bare_title",
        ),
    ],
)
@pytest.mark.usefixtures(
    "current_request_with_host", "mock_setup_entry", "mock_abrp_client"
)
async def test_entry_title_uses_display_name(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    payload: dict[str, Any],
    expected_title: str,
) -> None:
    """The title appends ``display_name`` when present, else uses the bare name.

    Resolving the display name from the OIDC claims is the library's concern;
    this only covers the two title-construction branches the flow itself owns.
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

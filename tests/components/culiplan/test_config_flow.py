"""Tests for the Culiplan config + options flow."""

from typing import Any
from unittest.mock import patch

import aiohttp
from aioresponses import aioresponses
import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.culiplan.config_flow import OAuth2FlowHandler
from homeassistant.components.culiplan.const import BASE_URL, DOMAIN, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CLIENT_ID = "ha-core"
CLIENT_SECRET = ""


@pytest.fixture
def aio() -> Any:
    """Yield an aioresponses fixture with localhost passthrough."""
    with aioresponses(passthrough=["http://127.0.0.1"]) as m:
        yield m


@pytest.fixture
async def credential(hass: HomeAssistant) -> None:
    """Register the public OAuth client credential."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(client_id=CLIENT_ID, client_secret=CLIENT_SECRET),
    )


async def _complete_oauth(
    hass: HomeAssistant,
    hass_client_no_auth: Any,
    aioclient_mock: AiohttpClientMocker,
    *,
    flow_id: str,
    access_token: str = "test-access-token",
) -> dict[str, Any]:
    """Walk an open OAuth2 flow through the redirect + token endpoints."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "refresh",
            "access_token": access_token,
            "type": "Bearer",
            "expires_in": 3600,
        },
    )
    return await hass.config_entries.flow.async_configure(flow_id)


async def test_full_oauth_flow_happy_path(
    hass: HomeAssistant,
    hass_client_no_auth: Any,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    credential: None,
) -> None:
    """Drive the full OAuth flow with a successful /api/users/me."""
    aioclient_mock.get(f"{BASE_URL}/api/users/me", json={"id": "user-42"})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    with patch(
        "homeassistant.components.culiplan.async_setup_entry", return_value=True
    ):
        result = await _complete_oauth(
            hass, hass_client_no_auth, aioclient_mock, flow_id=result["flow_id"]
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "user-42"


async def test_full_oauth_flow_duplicate_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: Any,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    credential: None,
) -> None:
    """A second add with the same account is aborted."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-42",
        data={"token": {"access_token": "x"}},
    ).add_to_hass(hass)

    aioclient_mock.get(f"{BASE_URL}/api/users/me", json={"id": "user-42"})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, flow_id=result["flow_id"]
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_oauth_flow_account_id_failure(
    hass: HomeAssistant,
    hass_client_no_auth: Any,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    credential: None,
) -> None:
    """If /api/users/me 500s, the entry is still created (no unique_id)."""
    aioclient_mock.get(f"{BASE_URL}/api/users/me", status=500)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.culiplan.async_setup_entry", return_value=True
    ):
        result = await _complete_oauth(
            hass, hass_client_no_auth, aioclient_mock, flow_id=result["flow_id"]
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


async def test_reconfigure_same_account(
    hass: HomeAssistant,
    hass_client_no_auth: Any,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    credential: None,
) -> None:
    """Reconfigure with same account updates token and reloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-42",
        data={"token": {"access_token": "old"}},
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{BASE_URL}/api/users/me", json={"id": "user-42"})

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.culiplan.async_setup_entry", return_value=True
    ):
        result = await _complete_oauth(
            hass,
            hass_client_no_auth,
            aioclient_mock,
            flow_id=result["flow_id"],
            access_token="brand-new-token",
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["token"]["access_token"] == "brand-new-token"


async def test_reconfigure_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: Any,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    credential: None,
) -> None:
    """Reconfigure as a different account aborts with ``wrong_account``."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-42",
        data={"token": {"access_token": "old"}},
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{BASE_URL}/api/users/me", json={"id": "different-user"})

    result = await entry.start_reconfigure_flow(hass)
    result = await _complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, flow_id=result["flow_id"]
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_reauth_flow(hass: HomeAssistant, credential: None) -> None:
    """Re-auth shows the confirm form first."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-42",
        data={"token": {"access_token": "old"}},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_completes_and_updates_token(
    hass: HomeAssistant,
    hass_client_no_auth: Any,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    credential: None,
) -> None:
    """Re-auth full round-trip updates the existing entry's token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-42",
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "stale", "refresh_token": "r"},
        },
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{BASE_URL}/api/users/me", json={"id": "user-42"})

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM

    # Click "Submit" to advance from reauth_confirm into the OAuth round-trip.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    with patch(
        "homeassistant.components.culiplan.async_setup_entry", return_value=True
    ):
        result = await _complete_oauth(
            hass,
            hass_client_no_auth,
            aioclient_mock,
            flow_id=result["flow_id"],
            access_token="refreshed-token",
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["access_token"] == "refreshed-token"


async def test_reauth_wrong_account_aborts(
    hass: HomeAssistant,
    hass_client_no_auth: Any,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    credential: None,
) -> None:
    """Re-auth with a different Culiplan account is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-42",
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "stale"},
        },
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{BASE_URL}/api/users/me", json={"id": "someone-else"})

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    result = await _complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, flow_id=result["flow_id"]
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_fetch_account_id_no_token(hass: HomeAssistant, credential: None) -> None:
    """Empty input returns None."""
    handler = OAuth2FlowHandler()
    handler.hass = hass
    assert await handler._fetch_account_id({}) is None
    assert await handler._fetch_account_id({"token": {}}) is None


async def test_fetch_account_id_non_200(
    hass: HomeAssistant, credential: None, aio: aioresponses
) -> None:
    """Non-200 returns None."""
    handler = OAuth2FlowHandler()
    handler.hass = hass
    aio.get(f"{BASE_URL}/api/users/me", status=403)
    assert await handler._fetch_account_id({"token": {"access_token": "x"}}) is None


async def test_fetch_account_id_no_id_field(
    hass: HomeAssistant, credential: None, aio: aioresponses
) -> None:
    """Missing ``id`` field returns None."""
    handler = OAuth2FlowHandler()
    handler.hass = hass
    aio.get(f"{BASE_URL}/api/users/me", payload={})
    assert await handler._fetch_account_id({"token": {"access_token": "x"}}) is None


async def test_fetch_account_id_network_error(
    hass: HomeAssistant, credential: None, aio: aioresponses
) -> None:
    """Network errors return None."""
    handler = OAuth2FlowHandler()
    handler.hass = hass
    aio.get(
        f"{BASE_URL}/api/users/me",
        exception=aiohttp.ClientError("boom"),
    )
    assert await handler._fetch_account_id({"token": {"access_token": "x"}}) is None


async def test_handler_logger() -> None:
    """``logger`` property is a module logger."""
    handler = OAuth2FlowHandler()
    assert handler.logger.name == "homeassistant.components.culiplan.config_flow"

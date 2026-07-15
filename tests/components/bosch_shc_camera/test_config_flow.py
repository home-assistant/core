"""Test the Bosch Smart Home Camera config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.bosch_shc_camera.config_flow import KEYCLOAK_BASE
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

TOKEN_RESPONSE = {
    "access_token": "mock-access-token",
    "refresh_token": "mock-refresh-token",
    "type": "Bearer",
    "expires_in": 60,
}


async def test_abort_if_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A second setup attempt aborts — this integration is single-instance.

    `manifest.json` sets `single_config_entry: true`, so HA-core's flow
    manager rejects the second `SOURCE_USER` flow with the built-in
    "single_instance_allowed" reason before `BoschCameraConfigFlow.
    async_step_user` (and its own `_abort_if_unique_id_configured` check)
    ever runs.
    """
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow_auto_login(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The auto_login menu choice completes the OAuth2 PKCE flow end to end."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["auto_login", "manual_login"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "auto_login"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"].startswith(f"{KEYCLOAK_BASE}/auth?")
    assert "code_challenge=" in result["url"]
    assert "code_challenge_method=S256" in result["url"]

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(f"{KEYCLOAK_BASE}/token", json=TOKEN_RESPONSE)

    with patch(
        "homeassistant.components.bosch_shc_camera.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bosch Smart Home Camera"
    assert result["data"]["bearer_token"] == "mock-access-token"
    assert result["data"]["refresh_token"] == "mock-refresh-token"
    assert len(mock_setup_entry.mock_calls) == 1

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == DOMAIN


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow_token_exchange_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A rejected token exchange aborts the flow instead of creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "auto_login"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        f"{KEYCLOAK_BASE}/token",
        status=400,
        json={"error": "invalid_grant"},
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_failed"
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A reauth flow updates the existing entry's tokens in place."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "auto_login"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        f"{KEYCLOAK_BASE}/token",
        json={**TOKEN_RESPONSE, "access_token": "new-access-token"},
    )

    with patch(
        "homeassistant.components.bosch_shc_camera.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["bearer_token"] == "new-access-token"
    # Reauth must not create a second entry — the existing one is updated in place.
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

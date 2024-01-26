"""Test the Husqvarna Automower config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.husqvarna_automower.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import load_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "husqvarna_automower", context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    token = load_fixture("jwt", DOMAIN)

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": token,
            "scope": "iam:read amc:api",
            "expires_in": 86399,
            "refresh_token": "mock-refresh-token",
            "provider": "husqvarna",
            "user_id": "mock-user-id",
            "token_type": "Bearer",
            "expires_at": 1697753347,
        },
    )

    with patch(
        "homeassistant.components.husqvarna_automower.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

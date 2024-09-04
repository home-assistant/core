"""Test the Weheat config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.weheat.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials,
) -> None:
    """Check full of adding a single heat pump."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await handle_oath(hass, hass_client_no_auth, aioclient_mock, result)

    with (
        patch(
            "homeassistant.components.weheat.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def handle_oath(hass, hass_client_no_auth, aioclient_mock, result):
    """Handle the Oauth2 part of the flow."""
    state = config_entry_oauth2_flow._encode_jwt(  # noqa: SLF001
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

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

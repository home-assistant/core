"""Test the Minut Point config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.point.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

REDIRECT_URL = "https://example.com/auth/external/callback"


@pytest.fixture(autouse=True)
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
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
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
            "user_id": "abcd",
        },
    )

    with patch(
        "homeassistant.components.point.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "abcd"
    assert result["result"].data["token"]["user_id"] == "abcd"
    assert result["result"].data["token"]["type"] == "Bearer"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
    assert result["result"].data["token"]["expires_in"] == 60
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert "webhook_id" in result["result"].data


@pytest.mark.parametrize(
    ("unique_id", "expected", "expected_unique_id"),
    [
        ("abcd", "reauth_successful", "abcd"),
        (None, "reauth_successful", "abcd"),
        ("abcde", "wrong_account", "abcde"),
    ],
    ids=("correct-unique_id", "missing-unique_id", "wrong-unique_id-abort"),
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_reauthentication_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    unique_id: str | None,
    expected: str,
    expected_unique_id: str,
) -> None:
    """Test reauthentication flow."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        version=1,
        data={"id": "timmo", "auth_implementation": DOMAIN},
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "user_id": "abcd",
        },
    )

    with (
        patch("homeassistant.components.point.api.AsyncConfigEntryAuth"),
        patch(
            f"homeassistant.components.{DOMAIN}.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected
    assert old_entry.unique_id == expected_unique_id

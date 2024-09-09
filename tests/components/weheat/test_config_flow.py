"""Test the Weheat config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.weheat.const import (
    DOMAIN,
    ENTRY_TITLE,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_SOURCE, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    CLIENT_ID,
    CONF_AUTH_IMPLEMENTATION,
    CONF_REFRESH_TOKEN,
    MOCK_ACCESS_TOKEN,
    MOCK_REFRESH_TOKEN,
    USER_UUID_1,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
) -> None:
    """Check full of adding a single heat pump."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    await handle_oauth(hass, hass_client_no_auth, aioclient_mock, result)

    with (
        patch(
            "homeassistant.components.weheat.config_flow.get_user_id_from_token",
            return_value=USER_UUID_1,
        ) as mock_weheat,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_weheat.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USER_UUID_1
    assert result["result"].title == ENTRY_TITLE
    assert result["data"][CONF_TOKEN][CONF_REFRESH_TOKEN] == MOCK_REFRESH_TOKEN
    assert result["data"][CONF_TOKEN][CONF_ACCESS_TOKEN] == MOCK_ACCESS_TOKEN
    assert result["data"][CONF_AUTH_IMPLEMENTATION] == DOMAIN


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_unique_id(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
) -> None:
    """Check that the config flow is aborted when an entry with the same ID exists."""
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id=USER_UUID_1,
    )

    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    await handle_oauth(hass, hass_client_no_auth, aioclient_mock, result)

    with (
        patch(
            "homeassistant.components.weheat.config_flow.get_user_id_from_token",
            return_value=USER_UUID_1,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # only care that the config flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def handle_oauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    result: ConfigFlowResult,
) -> None:
    """Handle the Oauth2 part of the flow."""
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
        "&scope=openid+offline_access"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": MOCK_REFRESH_TOKEN,
            "access_token": MOCK_ACCESS_TOKEN,
            "type": "Bearer",
            "expires_in": 60,
        },
    )

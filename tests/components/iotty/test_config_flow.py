"""Test the iotty config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import multidict
import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.iotty.application_credentials import OAUTH2_TOKEN
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .conftest import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup application credentials component."""
    await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def current_request_with_host(current_request: MagicMock) -> None:
    """Mock current request with a host header."""
    new_headers = multidict.CIMultiDict(current_request.get.return_value.headers)
    new_headers[config_entry_oauth2_flow.HEADER_FRONTEND_BASE] = "https://example.com"
    current_request.get.return_value = current_request.get.return_value.clone(
        headers=new_headers
    )


async def test_config_flow_no_credentials(hass: HomeAssistant) -> None:
    """Test config flow base case with no credentials registered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "missing_credentials"


@pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Check full flow."""

    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER, "entry_id": DOMAIN}
    )

    assert result.get("type") == FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
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

    await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1

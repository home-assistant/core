"""Tests for the Overkiz Rexel OAuth2 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from pyoverkiz.client import GatewayCandidate
from pyoverkiz.const import (
    REXEL_OAUTH_AUTHORIZE_URL,
    REXEL_OAUTH_POLICY,
    REXEL_OAUTH_TOKEN_URL,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"

TEST_GATEWAY_ID = "1234-5678-9123"
TEST_GATEWAY_ID2 = "9876-5432-1000"

REDIRECT_URI = "https://example.com/auth/external/callback"

pytestmark = pytest.mark.usefixtures("current_request_with_host")


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up the application credential used by the Rexel OAuth2 flow."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, ""),
        DOMAIN,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.overkiz.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def _async_oauth_external_step(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
) -> None:
    """Drive the OAuth2 external step and stub the token exchange."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {"flow_id": flow_id, "redirect_uri": REDIRECT_URI},
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        REXEL_OAUTH_TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )


async def test_full_flow_single_gateway(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """A single-gateway account auto-selects and creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert REXEL_OAUTH_AUTHORIZE_URL in result["url"]
    # Azure AD B2C needs the policy on the authorize URL; the helper rebuilds
    # the query string, so it must survive via extra_authorize_data.
    assert f"p={REXEL_OAUTH_POLICY}" in result["url"]

    await _async_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="My Home")],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Home"
    assert result["result"].unique_id == TEST_GATEWAY_ID
    assert result["data"]["hub"] == "rexel"
    assert result["data"]["gateway_id"] == TEST_GATEWAY_ID
    assert "token" in result["data"]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_flow_multiple_gateways(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """A multi-gateway account shows a selection step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )
    await _async_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[
            GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="Home"),
            GatewayCandidate(gateway_id=TEST_GATEWAY_ID2, label="Office"),
        ],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"gateway_id": TEST_GATEWAY_ID2}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Office"
    assert result["result"].unique_id == TEST_GATEWAY_ID2
    assert result["data"]["gateway_id"] == TEST_GATEWAY_ID2
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_no_gateways(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An account without gateways aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )
    await _async_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_gateways"


async def test_flow_cannot_connect(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A gateway discovery error aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"hub": "rexel"}
    )
    await _async_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        side_effect=ClientError,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Reauth with a different gateway aborts."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "old-token"},
            "hub": "rexel",
            "gateway_id": TEST_GATEWAY_ID,
        },
    )
    config_entry.add_to_hass(hass)

    # Reauth carries the stored hub, so the flow goes straight to the OAuth2
    # external step without showing the server picker again.
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _async_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[GatewayCandidate(gateway_id=TEST_GATEWAY_ID2, label="Other")],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_wrong_account"


async def test_reauth_success(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Reauth with the same gateway updates the entry and reloads."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "old-token"},
            "hub": "rexel",
            "gateway_id": TEST_GATEWAY_ID,
        },
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    await _async_oauth_external_step(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )

    with patch(
        "homeassistant.components.overkiz.config_flow.OverkizClient.discover_gateways",
        return_value=[GatewayCandidate(gateway_id=TEST_GATEWAY_ID, label="My Home")],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["token"]["access_token"] == "mock-access-token"

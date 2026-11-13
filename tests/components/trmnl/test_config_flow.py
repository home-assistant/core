"""Test the TRMNL config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock

from aiohttp import ClientError
import jwt
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.plugins import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError
from yarl import URL

from homeassistant.components.trmnl.const import (
    CLIENT_ID,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_REVOKE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import ACCOUNT_SUBJECT

REDIRECT_URI = "https://example.com/auth/external/callback"


async def complete_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    result: ConfigFlowResult,
    subject: str | None = ACCOUNT_SUBJECT,
    scope: str = "openid profile read devices content delete",
) -> ConfigFlowResult:
    """Sign in on TRMNL and come back to Home Assistant with a token."""
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(OAUTH2_REVOKE)
    token = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": 7200,
        "token_type": "Bearer",
        "scope": scope,
    }
    if subject:
        token["id_token"] = jwt.encode({"sub": subject}, key="secret")
    aioclient_mock.post(OAUTH2_TOKEN, json=token)
    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("current_request_with_host", "mock_trmnl_client")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test signing in with TRMNL creates an entry for the account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    authorize_url = URL(result["url"])
    assert f"{authorize_url.origin()}{authorize_url.path}" == OAUTH2_AUTHORIZE
    assert authorize_url.query["client_id"] == CLIENT_ID
    assert authorize_url.query["redirect_uri"] == REDIRECT_URI
    assert authorize_url.query["scope"] == "openid profile read devices content delete"
    assert authorize_url.query["code_challenge_method"] == "S256"

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test"
    assert result["result"].unique_id == ACCOUNT_SUBJECT
    assert result["data"]["token"]["access_token"] == "access"
    assert len(mock_setup_entry.mock_calls) == 1
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_flow_without_profile_scope(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test the entry is named TRMNL when the user unticks the profile scope."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result, scope="openid read devices"
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TRMNL"
    mock_trmnl_client.get_me.assert_not_called()


@pytest.mark.usefixtures("current_request_with_host", "mock_trmnl_client")
async def test_flow_without_device_scopes(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the flow aborts when the user unticks a scope the devices need."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result, scope="openid read"
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_scopes"


@pytest.mark.usefixtures("current_request_with_host", "mock_trmnl_client")
async def test_flow_without_account_identity(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the flow aborts when the user did not let TRMNL sign them in."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result, subject=None
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_account_identity"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (TRMNLError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (TRMNLAuthenticationError, "oauth_unauthorized"),
    ],
)
async def test_flow_cannot_read_devices(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_trmnl_client: AsyncMock,
    error: type[Exception],
    reason: str,
) -> None:
    """Test the flow aborts when the token cannot list devices."""
    mock_trmnl_client.get_devices.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("current_request_with_host", "mock_trmnl_client")
async def test_duplicate_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test signing in to an account that is already set up."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert aioclient_mock.mock_calls[-1][2] == {
        "token": "access",
        "client_id": CLIENT_ID,
    }


DHCP_DISCOVERY = DhcpServiceInfo(
    ip="192.168.1.10",
    hostname="trmnl-og-1rjxs4",
    macaddress="b0a604aabbcc",
)


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_trmnl_client", "mock_setup_entry"
)
async def test_dhcp_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test DHCP discovery asks before it starts the sign in, then creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "oauth_discovery"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == ACCOUNT_SUBJECT


async def test_dhcp_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test DHCP discovery aborts when an account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_already_in_progress(hass: HomeAssistant) -> None:
    """Test only one DHCP discovery flow is started."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.11",
            hostname="trmnl-og-2abcd5",
            macaddress="b0a604ddeeff",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_trmnl_client", "mock_setup_entry"
)
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test signing in again replaces the token."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data["token"]["refresh_token"] == "refresh"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_trmnl_client", "mock_setup_entry"
)
async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth aborts when the user signs in to another account."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result, subject="someone-else"
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_trmnl_client", "mock_setup_entry"
)
async def test_reconfigure_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test signing in again from Reconfigure replaces the token and keeps the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result, scope="openid read devices"
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data["token"]["scope"] == "openid read devices"
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]


@pytest.mark.usefixtures(
    "current_request_with_host", "mock_trmnl_client", "mock_setup_entry"
)
async def test_reconfigure_flow_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Reconfigure aborts when the user signs in to another account."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result, subject="someone-else"
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data["token"]["access_token"] == "access"
    assert aioclient_mock.mock_calls[-1][1] == URL(OAUTH2_REVOKE)


@pytest.mark.usefixtures("current_request_with_host", "mock_trmnl_client")
async def test_abort_when_token_cannot_be_revoked(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the flow still aborts when TRMNL cannot be reached to revoke the token."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    aioclient_mock.post(OAUTH2_REVOKE, exc=ClientError)

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_trmnl_client")
@pytest.mark.parametrize("entity_id", ["light.lamp", "climate.living_room"])
async def test_options_flow_picks_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, entity_id: str
) -> None:
    """Test the options flow stores the entities to show on TRMNL."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"home_entities": [entity_id]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {"home_entities": [entity_id]}


@pytest.mark.usefixtures("mock_trmnl_client")
async def test_options_flow_needs_content_scope(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test picking entities asks for a new sign in when content was unticked."""
    token = {**mock_config_entry.data["token"], "scope": "openid read devices"}
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": token}
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"home_entities": ["light.lamp"]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "content_not_granted"
    assert mock_config_entry.options == {}
    assert [
        flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()
    ] == [SOURCE_REAUTH]


@pytest.mark.usefixtures("current_request_with_host", "mock_trmnl_client")
async def test_revoke_refused_is_logged(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a revoke TRMNL refuses is logged."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    aioclient_mock.post(OAUTH2_REVOKE, status=HTTPStatus.BAD_REQUEST)

    await complete_oauth_flow(hass, hass_client_no_auth, aioclient_mock, result)

    assert "Could not revoke an unused TRMNL token" in caplog.text


@pytest.mark.usefixtures("current_request_with_host", "mock_trmnl_client")
async def test_abort_keeps_shared_translation(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test an abort raised by core keeps the translation domain core gave it."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "unique_id": ACCOUNT_SUBJECT}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await complete_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
    assert result["translation_domain"] == "homeassistant"

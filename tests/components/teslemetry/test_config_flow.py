"""Test the Teslemetry config flow."""

from collections.abc import Generator
from copy import deepcopy
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientConnectionError, ClientError, ClientResponseError, RequestInfo
from aiopowerwall import (
    DEFAULT_GATEWAY_HOST,
    PowerwallAuthenticationError,
    PowerwallConnectionError,
    PowerwallFaultError,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from multidict import CIMultiDict
import pytest
from tesla_fleet_api.const import AuthorizedClientState
from tesla_fleet_api.exceptions import (
    InvalidResponse,
    InvalidToken,
    ResponseError,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.teslemetry.energysite import AuthorizedClient, AuthorizedClients
from yarl import URL

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.teslemetry.const import (
    AUTHORIZE_URL,
    CLIENT_ID,
    CONF_SITE_ID,
    DOMAIN,
    SUBENTRY_TYPE_ENERGY_SITE,
    TOKEN_URL,
)
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryState,
    ConfigSubentryData,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.setup import async_setup_component

from . import mock_config_entry, setup_platform
from .const import CONFIG_V1, METADATA, PRODUCTS, UNIQUE_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT = "https://example.com/auth/external/callback"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    assert result["url"].startswith(AUTHORIZE_URL)
    parsed_url = urlparse(result["url"])
    parsed_query = parse_qs(parsed_url.query)
    assert parsed_query["response_type"][0] == "code"
    assert parsed_query["client_id"][0] == CLIENT_ID
    assert parsed_query["redirect_uri"][0] == REDIRECT
    assert parsed_query["state"][0] == state
    assert parsed_query["code_challenge"][0]

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    response = {
        "refresh_token": "test_refresh_token",
        "access_token": "test_access_token",
        "type": "Bearer",
        "expires_in": 60,
    }

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json=response,
    )

    # Complete OAuth
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UNIQUE_ID
    assert result["data"]["auth_implementation"] == "teslemetry"
    assert result["data"]["token"]["refresh_token"] == response["refresh_token"]
    assert result["data"]["token"]["access_token"] == response["access_token"]
    assert result["data"]["token"]["type"] == response["type"]
    assert result["data"]["token"]["expires_in"] == response["expires_in"]
    assert "expires_at" in result["result"].data["token"]


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth flow."""

    mock_entry = await setup_platform(hass, [])

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    # Progress from reauth_confirm to external OAuth step
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "test_refresh_token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def _complete_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    entry: MockConfigEntry,
) -> MagicMock:
    """Drive a reauth flow to completion and return the schedule_reload mock."""
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "test_refresh_token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_schedule_reload:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    return mock_schedule_reload


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_loaded_schedules_reload(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A data-only reauth schedules the reload itself to apply the token.

    The subentry set is unchanged, so the update listener never reloads.
    """
    mock_entry = await setup_platform(hass, [])
    assert mock_entry.state is ConfigEntryState.LOADED

    mock_schedule_reload = await _complete_reauth(
        hass, hass_client_no_auth, aioclient_mock, mock_entry
    )
    mock_schedule_reload.assert_called_once_with(mock_entry.entry_id)


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_not_loaded_schedules_reload(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An unloaded entry has no update listener, so the flow schedules the reload."""
    mock_entry = mock_config_entry()
    mock_entry.add_to_hass(hass)
    # A failed setup imports the client credential before it aborts, so mirror that
    # while leaving the entry unloaded (and therefore without an update listener).
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, "", name="Teslemetry")
    )
    assert mock_entry.state is ConfigEntryState.NOT_LOADED

    mock_schedule_reload = await _complete_reauth(
        hass, hass_client_no_auth, aioclient_mock, mock_entry
    )
    mock_schedule_reload.assert_called_once_with(mock_entry.entry_id)


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Tesla Fleet reauthentication with different account."""
    # Create an entry with a different unique_id to test account mismatch
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="baduid",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old_access_token",
                "refresh_token": "old_refresh_token",
                "expires_at": int(time.time()) + 3600,
            },
        },
    )
    old_entry.add_to_hass(hass)

    # Setup the integration properly to import client credentials
    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    result = await old_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_unique_id_abort(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test duplicate unique ID aborts flow."""
    # Create existing entry
    await setup_platform(hass, [])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    # Complete OAuth - should abort due to duplicate unique_id
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "exception",
    [
        InvalidToken,
        SubscriptionRequired,
        ClientConnectionError,
        TeslaFleetError("API error"),
    ],
)
async def test_oauth_error_handling(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    exception: Exception,
) -> None:
    """Test OAuth flow with various API errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )

    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "test_refresh_token",
            "access_token": "test_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure flow."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    new_token_response = mock_token_response | {
        "refresh_token": "new_refresh_token",
        "access_token": "new_access_token",
    }
    aioclient_mock.post(TOKEN_URL, json=new_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify entry data was updated
    assert mock_entry.data["auth_implementation"] == DOMAIN
    assert mock_entry.data["token"]["refresh_token"] == "new_refresh_token"
    assert mock_entry.data["token"]["access_token"] == "new_access_token"
    assert mock_entry.data["token"]["type"] == "Bearer"
    assert mock_entry.data["token"]["expires_in"] == 60
    assert "expires_at" in mock_entry.data["token"]


@pytest.mark.usefixtures("current_request_with_host")
async def test_reconfigure_not_loaded_schedules_reload(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Reconfiguring an unloaded entry has no update listener, so the flow reloads."""
    mock_entry = mock_config_entry()
    mock_entry.add_to_hass(hass)
    # A failed setup imports the client credential before it aborts, so mirror that
    # while leaving the entry unloaded (and therefore without an update listener).
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, "", name="Teslemetry")
    )
    assert mock_entry.state is ConfigEntryState.NOT_LOADED

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    new_token_response = mock_token_response | {
        "refresh_token": "new_refresh_token",
        "access_token": "new_access_token",
    }
    aioclient_mock.post(TOKEN_URL, json=new_token_response)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_schedule_reload:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data["token"]["refresh_token"] == "new_refresh_token"
    mock_schedule_reload.assert_called_once_with(mock_entry.entry_id)


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure with different account."""
    # Create an entry with a different unique_id to test account mismatch
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="baduid",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old_access_token",
                "refresh_token": "old_refresh_token",
                "expires_at": int(time.time()) + 3600,
            },
        },
    )
    old_entry.add_to_hass(hass)

    # Setup the integration properly to import client credentials
    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    result = await old_entry.start_reconfigure_flow(hass)

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "exception",
    [
        InvalidToken,
        SubscriptionRequired,
        ClientConnectionError,
        TeslaFleetError("API error"),
    ],
)
async def test_reconfigure_oauth_error_handling(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
    exception: Exception,
) -> None:
    """Test reconfigure flow with various API errors."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_oauth_error_recovery(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_token_response: dict[str, Any],
) -> None:
    """Test reconfigure flow can recover from an OAuth error."""
    mock_entry = await setup_platform(hass, [])
    client = await hass_client_no_auth()

    # First attempt - simulate OAuth error
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)

    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata",
        side_effect=ClientConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"

    # Second attempt - should succeed (recovery)
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT,
        },
    )
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.clear_requests()
    new_token_response = mock_token_response | {
        "refresh_token": "new_refresh_token",
        "access_token": "new_access_token",
    }
    aioclient_mock.post(TOKEN_URL, json=new_token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify entry data was updated after recovery
    assert mock_entry.data["token"]["refresh_token"] == "new_refresh_token"
    assert mock_entry.data["token"]["access_token"] == "new_access_token"


async def test_migrate_error_from_future(
    hass: HomeAssistant, mock_metadata: AsyncMock
) -> None:
    """Test a future version isn't migrated."""

    mock_metadata.side_effect = TeslaFleetError

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        minor_version=1,
        unique_id="abc-123",
        data=CONFIG_V1,
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


SITE_ID = 123456
WALL_CONNECTOR_SITE_ID = 555555
HOST = "192.168.91.1"
PASSWORD = "abcde"
# Matches the paired site's `gateway_id` in the products fixture.
GATEWAY_DIN = "ABC123"
PUBLIC_KEY_DER = b"public-key-der"
PUBLIC_KEY_B64 = "cHVibGljLWtleS1kZXI="

# aiopowerwall's PowerwallClient parses the PEM at construction time, so tests
# that build one need a real (if undersized, for speed) RSA key rather than
# arbitrary bytes.
_TEST_RSA_KEY_PEM = rsa.generate_private_key(
    public_exponent=65537, key_size=1024
).private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)

# A bodyless 502 surfaces as ResponseError; one with a JSON body as
# ClientResponseError. Both are the gateway-unreachable condition.
POWERWALL_502_ERRORS = [
    pytest.param(ResponseError(status=502), id="response_error"),
    pytest.param(ClientResponseError(None, (), status=502), id="client_response_error"),
]

# A well-formed non-502 ClientResponseError; a real one carries request_info,
# so it renders when logged, unlike the bodyless 502 fixtures above.
_NON_502_CLIENT_RESPONSE_ERROR = ClientResponseError(
    RequestInfo(URL("http://gateway"), "GET", CIMultiDict()), (), status=500
)


def _entry_with_powerwall() -> MockConfigEntry:
    """Return a config entry whose energy site subentry is already paired."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
                unique_id=str(SITE_ID),
                title="Energy Site",
                data={
                    CONF_SITE_ID: SITE_ID,
                    CONF_HOST: HOST,
                    CONF_PASSWORD: PASSWORD,
                },
            )
        ],
    )


@pytest.fixture(autouse=True)
def mock_gateway_discovery() -> Generator[AsyncMock]:
    """Default gateway-address discovery to no result."""
    with patch(
        "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address",
        new=AsyncMock(return_value=None),
    ) as mock_find:
        yield mock_find


@pytest.fixture
def mock_rsa_key() -> Generator[None]:
    """Mock RSA key generation/loading, avoiding real crypto and disk I/O."""
    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.Teslemetry.get_rsa_private_key",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.Teslemetry.rsa_public_der_pkcs1",
            new_callable=PropertyMock,
            return_value=PUBLIC_KEY_DER,
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.Teslemetry.rsa_public_der_pkcs1_b64",
            new_callable=PropertyMock,
            return_value=PUBLIC_KEY_B64,
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.Path.read_bytes",
            return_value=_TEST_RSA_KEY_PEM,
        ),
    ):
        yield


def _mock_powerwall_client(
    *,
    connect_error: Exception | None = None,
    din: str = GATEWAY_DIN,
    status_error: Exception | None = None,
) -> MagicMock:
    """Return a mock aiopowerwall PowerwallClient async context manager."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.connect = AsyncMock(return_value=din, side_effect=connect_error)
    client.get_status = AsyncMock(side_effect=status_error)
    return client


def _own_key_clients(
    state: AuthorizedClientState | int | str | None,
) -> AuthorizedClients:
    """Return a typed client list carrying our key in the given state."""
    return AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key="some-other-key",
                state=AuthorizedClientState.VERIFIED,
                roles=None,
                verification=None,
                raw={},
            ),
            AuthorizedClient(
                public_key=PUBLIC_KEY_B64,
                state=state,
                roles=None,
                verification=None,
                raw={},
            ),
        ],
        raw=None,
    )


def _empty_clients() -> AuthorizedClients:
    """Return a typed client list that is authoritatively empty."""
    return AuthorizedClients(clients=[], raw=None)


async def _start_add_flow_select_site(
    hass: HomeAssistant, entry: MockConfigEntry
) -> SubentryFlowResult:
    """Start the add flow and select the battery site, returning the next step."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )
    assert result["step_id"] == "user"
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_SITE_ID: str(SITE_ID)}
    )


async def _setup_account_no_subentry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an account entry with no local-control subentry (nothing opted in)."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _credentials_host_default(result: SubentryFlowResult) -> str:
    """Return the CONF_HOST field's schema default from a credentials form result."""
    for key in result["data_schema"].schema:
        if key == CONF_HOST:
            return key.default()
    raise AssertionError("CONF_HOST field not found in credentials schema")


@pytest.mark.usefixtures("mock_rsa_key")
async def test_energy_subentry_pairing_requires_key_approval(
    hass: HomeAssistant,
) -> None:
    """Pairing registers the key, then advances to credentials once approved."""
    entry = await _setup_account_no_subentry(hass)

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                side_effect=[
                    _empty_clients(),
                    _own_key_clients(AuthorizedClientState.PENDING_VERIFICATION),
                    _own_key_clients(AuthorizedClientState.VERIFIED),
                ]
            ),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        mock_add.assert_awaited_once()

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert result["errors"] == {"base": "key_pending"}

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    assert subentry.data[CONF_HOST] == HOST


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_null_body_aborts_as_lookup_failure(hass: HomeAssistant) -> None:
    """A malformed authorized-clients read aborts rather than registering."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(side_effect=InvalidResponse),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    mock_add.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    ("client_kwargs", "expected_error"),
    [
        pytest.param(
            {"connect_error": PowerwallAuthenticationError()},
            "invalid_password",
            id="wrong_gateway_password",
        ),
        pytest.param(
            {"connect_error": PowerwallConnectionError()},
            "cannot_connect",
            id="gateway_unreachable",
        ),
        pytest.param(
            {"status_error": PowerwallAuthenticationError()},
            "key_not_approved",
            id="signed_read_rejects_unapproved_key",
        ),
        pytest.param(
            {"status_error": PowerwallFaultError("MESSAGEFAULT_ERROR_BUSY")},
            "cannot_connect",
            id="signed_read_generic_gateway_fault",
        ),
        pytest.param(
            {"status_error": PowerwallConnectionError()},
            "cannot_connect",
            id="signed_read_unreachable",
        ),
    ],
)
async def test_subentry_credentials_errors(
    hass: HomeAssistant,
    client_kwargs: dict[str, Exception],
    expected_error: str,
) -> None:
    """The credentials step reports each local verification failure distinctly."""
    entry = await _setup_account_no_subentry(hass)

    client = _mock_powerwall_client(**client_kwargs)
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": expected_error}
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_prefills_discovered_host(
    hass: HomeAssistant,
) -> None:
    """A discovered gateway address pre-fills the credentials CONF_HOST default."""
    entry = await _setup_account_no_subentry(hass)
    discovered_host = "192.168.1.138"

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address",
            new=AsyncMock(return_value=discovered_host),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert _credentials_host_default(result) == discovered_host


@pytest.mark.usefixtures("mock_rsa_key")
async def test_add_flow_lists_only_not_added_sites(hass: HomeAssistant) -> None:
    """The add flow offers battery sites that have not already been added."""
    entry = await _setup_account_no_subentry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema = result["data_schema"].schema
    site_field = next(iter(schema))
    assert site_field == CONF_SITE_ID
    # Only the battery-capable site is selectable; the componentless site is not.
    assert set(schema[site_field].container) == {str(SITE_ID)}


async def test_add_flow_aborts_when_all_sites_added(hass: HomeAssistant) -> None:
    """The add flow aborts when every battery site is already paired."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_energy_sites"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_add_flow_creates_subentry_bound_to_existing_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The add flow creates a subentry for the site and reuses its device."""
    entry = await _setup_account_no_subentry(hass)
    devices_before = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    site_device = next(
        device
        for device in devices_before
        if (DOMAIN, str(SITE_ID)) in device.identifiers
    )

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
            context={"source": "user"},
        )
        assert result["step_id"] == "user"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_SITE_ID: str(SITE_ID)}
        )
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    assert subentry.unique_id == str(SITE_ID)
    assert subentry.data[CONF_SITE_ID] == SITE_ID
    assert subentry.data[CONF_HOST] == HOST
    assert subentry.data[CONF_PASSWORD] == PASSWORD

    # No duplicate device: the same site device is reused.
    site_devices = [
        device
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if (DOMAIN, str(SITE_ID)) in device.identifiers
    ]
    assert [device.id for device in site_devices] == [site_device.id]


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_password_truncated(hass: HomeAssistant) -> None:
    """A full Wi-Fi password is trimmed to its final five characters."""
    entry = await _setup_account_no_subentry(hass)

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ) as mock_client,
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: "long-wifi-password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    assert subentry.data[CONF_PASSWORD] == "sword"
    assert mock_client.call_args.kwargs["gateway_password"] == "sword"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_wall_connector_only_site_not_offered_for_local_control(
    hass: HomeAssistant,
) -> None:
    """A wall-connector-only site can't do local control; only a Powerwall can."""
    products = deepcopy(PRODUCTS)
    products["response"].append(
        {
            "energy_site_id": WALL_CONNECTOR_SITE_ID,
            "site_name": "Wall Connector Site",
            "components": {
                "battery": False,
                "solar": False,
                "grid": True,
                "wall_connectors": [{"device_id": "wc-1", "din": "WC-DIN-1"}],
            },
        }
    )
    metadata = deepcopy(METADATA)
    metadata["energy_sites"][str(WALL_CONNECTOR_SITE_ID)] = {
        "access": True,
        "name": "Wall Connector Site",
    }

    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch("tesla_fleet_api.teslemetry.Teslemetry.products", return_value=products),
        patch("tesla_fleet_api.teslemetry.Teslemetry.metadata", return_value=metadata),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )
    schema = result["data_schema"].schema
    site_field = next(iter(schema))
    assert set(schema[site_field].container) == {str(SITE_ID)}


async def test_add_flow_aborts_when_entry_not_loaded(hass: HomeAssistant) -> None:
    """The add flow aborts when the account entry is not loaded."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_gateway_discovery_failure_proceeds_without_host(
    hass: HomeAssistant,
) -> None:
    """A failed gateway-address discovery leaves the host default unset."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address",
            new=AsyncMock(side_effect=ClientError),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert _credentials_host_default(result) == DEFAULT_GATEWAY_HOST


@pytest.mark.usefixtures("mock_rsa_key")
async def test_pending_key_resumes_without_reregister(hass: HomeAssistant) -> None:
    """A key already pending on the gateway resumes pairing without re-adding it."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(
                    AuthorizedClientState.PENDING_VERIFICATION
                )
            ),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    mock_add.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_timed_out_key_reregisters_for_a_fresh_window(
    hass: HomeAssistant,
) -> None:
    """A key whose approval window expired is re-registered, not left stuck."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(
                    AuthorizedClientState.PENDING_VERIFICATION_TIMEOUT
                )
            ),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    mock_add.assert_awaited_once()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_unrecognized_state_aborts_pairing(hass: HomeAssistant) -> None:
    """An unrecognized authorized-client state aborts rather than re-registering."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_own_key_clients("gremlin")),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    mock_add.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_add_authorized_client_failure_aborts(hass: HomeAssistant) -> None:
    """A failure while registering the key aborts the flow."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_empty_clients()),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(side_effect=ClientError),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    ("second_lookup", "expected_error"),
    [
        pytest.param(InvalidResponse(), "cannot_connect", id="lookup_failure"),
        pytest.param(_empty_clients(), "key_not_registered", id="key_not_registered"),
        pytest.param(_own_key_clients("gremlin"), "cannot_connect", id="unknown_state"),
    ],
)
async def test_pair_step_second_lookup_errors(
    hass: HomeAssistant,
    second_lookup: Exception | AuthorizedClients,
    expected_error: str,
) -> None:
    """Re-checking the pending key reports each non-approval outcome on the form."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(side_effect=[_empty_clients(), second_lookup]),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["step_id"] == "pair"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize("error", POWERWALL_502_ERRORS)
async def test_pairing_verify_powerwall_unreachable(
    hass: HomeAssistant, error: Exception
) -> None:
    """A 502 while checking the key aborts with the retryable message."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(side_effect=error),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "powerwall_unreachable"
    mock_add.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize("error", POWERWALL_502_ERRORS)
async def test_pairing_add_client_powerwall_unreachable(
    hass: HomeAssistant, error: Exception
) -> None:
    """A 502 while registering the key aborts with the retryable message."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_empty_clients()),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(side_effect=error),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "powerwall_unreachable"


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TeslaFleetError(), id="tesla_fleet_error"),
        pytest.param(_NON_502_CLIENT_RESPONSE_ERROR, id="client_response_error"),
    ],
)
async def test_pairing_add_client_generic_error_aborts(
    hass: HomeAssistant, error: Exception
) -> None:
    """A non-502 error while registering the key aborts cleanly, never crashes."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_empty_clients()),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(side_effect=error),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize("error", POWERWALL_502_ERRORS)
async def test_pair_step_powerwall_unreachable(
    hass: HomeAssistant, error: Exception
) -> None:
    """A 502 while checking approval on submit re-shows the pair form as retryable."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(side_effect=[_empty_clients(), error]),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["step_id"] == "pair"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "powerwall_unreachable"}


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    ("patch_target", "error"),
    [
        pytest.param(
            "homeassistant.components.teslemetry.config_flow.Teslemetry.get_rsa_private_key",
            OSError,
            id="key_fetch_oserror",
        ),
        pytest.param(
            "homeassistant.components.teslemetry.config_flow.Path.read_bytes",
            ValueError,
            id="key_read_valueerror",
        ),
    ],
)
async def test_rsa_key_load_failure_aborts(
    hass: HomeAssistant,
    patch_target: str,
    error: type[Exception],
) -> None:
    """A failure loading the integration's RSA key aborts site preparation."""
    entry = await _setup_account_no_subentry(hass)

    with patch(patch_target, side_effect=error):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

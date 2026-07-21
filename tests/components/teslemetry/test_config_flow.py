"""Test the Teslemetry config flow."""

import base64
from collections.abc import Generator
import time
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientConnectionError, ClientResponseError, RequestInfo
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from multidict import CIMultiDict
import pytest
from tesla_fleet_api.const import AuthorizedClientState
from tesla_fleet_api.exceptions import (
    InvalidToken,
    ResponseError,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.teslemetry import Teslemetry
from tesla_fleet_api.teslemetry.energysite import (
    AuthorizedClient,
    AuthorizedClients,
    TeslemetryEnergySite,
)
from yarl import URL

from homeassistant.components.teslemetry.config_flow import (
    _authorized_client_from_local,
    _is_gateway_unreachable,
)
from homeassistant.components.teslemetry.const import (
    AUTHORIZE_URL,
    CLIENT_ID,
    DOMAIN,
    SUBENTRY_TYPE_ENERGY_SITE,
    TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import setup_platform
from .const import CONFIG_V1, UNIQUE_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT = "https://example.com/auth/external/callback"

# A small key generated once keeps the pairing-flow tests off the slow
# RSA-4096 keygen path; the flow only reads its public bytes, never its size.
_TEST_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_RSA_PEM = _TEST_RSA_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)
# The base64 DER PKCS1 public key the flow matches gateway clients against.
_TEST_PUBLIC_KEY_B64 = base64.b64encode(
    _TEST_RSA_KEY.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.PKCS1,
    )
).decode("ascii")

# A well-formed non-502 ClientResponseError; a real one carries request_info,
# so it renders when logged, unlike the bodyless 502 fixtures below.
_NON_502_CLIENT_RESPONSE_ERROR = ClientResponseError(
    RequestInfo(URL("http://gateway"), "GET", CIMultiDict()), (), status=500
)


@pytest.fixture
def mock_rsa_key() -> Generator[None]:
    """Provide the pairing flow a ready RSA key instead of generating one."""

    async def _fake_get_rsa_private_key(
        self: Teslemetry, path: str, key_size: int = 4096
    ) -> rsa.RSAPrivateKey:
        self.rsa_private_key = _TEST_RSA_KEY
        return _TEST_RSA_KEY

    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.Teslemetry.get_rsa_private_key",
            _fake_get_rsa_private_key,
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.Path.read_bytes",
            return_value=_TEST_RSA_PEM,
        ),
    ):
        yield


def _energy_subentry_id(entry: MockConfigEntry) -> str:
    """Return the energy-site subentry id created during setup."""
    return next(
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_ENERGY_SITE
    )


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


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(TeslaFleetError(), False, id="tesla_fleet_error_no_status"),
        pytest.param(ResponseError(status=502), True, id="response_error_502"),
        pytest.param(
            ClientResponseError(None, (), status=500),
            False,
            id="client_response_error_500",
        ),
    ],
)
def test_is_gateway_unreachable(error: Exception, expected: bool) -> None:
    """A bare TeslaFleetError has no status set and must not raise AttributeError."""
    assert _is_gateway_unreachable(error) is expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        pytest.param("VERIFIED", AuthorizedClientState.VERIFIED, id="verified"),
        pytest.param("PENDING", AuthorizedClientState.PENDING, id="pending"),
        pytest.param("SOME_FUTURE_STATE", "SOME_FUTURE_STATE", id="unrecognized"),
    ],
)
def test_authorized_client_from_local(
    state: str, expected: AuthorizedClientState | str
) -> None:
    """An unrecognized local state is kept verbatim rather than dropped."""
    client = _authorized_client_from_local({"public_key": "abc", "state": state})
    assert client.public_key == "abc"
    assert client.state == expected


POWERWALL_502_ERRORS = [
    pytest.param(ResponseError(status=502), id="response_error"),
    pytest.param(ClientResponseError(None, (), status=502), id="client_response_error"),
]


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize("error", POWERWALL_502_ERRORS)
async def test_energy_subentry_verify_powerwall_unreachable(
    hass: HomeAssistant,
    error: Exception,
) -> None:
    """A 502 while checking the key aborts with the retryable message."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    with patch.object(
        TeslemetryEnergySite,
        "find_authorized_clients",
        AsyncMock(side_effect=error),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "powerwall_unreachable"


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize("error", POWERWALL_502_ERRORS)
async def test_energy_subentry_add_client_powerwall_unreachable(
    hass: HomeAssistant,
    error: Exception,
) -> None:
    """A 502 while registering the key aborts with the retryable message."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(return_value=AuthorizedClients(clients=[], raw=None)),
        ),
        patch.object(
            TeslemetryEnergySite,
            "add_authorized_client",
            AsyncMock(side_effect=error),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

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
async def test_energy_subentry_add_client_generic_error(
    hass: HomeAssistant,
    error: Exception,
) -> None:
    """A non-502 error while registering the key aborts cleanly, never crashes."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(return_value=AuthorizedClients(clients=[], raw=None)),
        ),
        patch.object(
            TeslemetryEnergySite,
            "add_authorized_client",
            AsyncMock(side_effect=error),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize("error", POWERWALL_502_ERRORS)
async def test_energy_subentry_pair_check_powerwall_unreachable(
    hass: HomeAssistant,
    error: Exception,
) -> None:
    """A 502 while checking approval on submit re-shows the pair form as retryable."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)
    empty = AuthorizedClients(clients=[], raw=None)

    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(side_effect=[empty, error]),
        ),
        patch.object(
            TeslemetryEnergySite,
            "add_authorized_client",
            AsyncMock(return_value={}),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert not result["errors"]

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "powerwall_unreachable"}


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TeslaFleetError(), id="tesla_fleet_error"),
        pytest.param(_NON_502_CLIENT_RESPONSE_ERROR, id="client_response_error"),
    ],
)
async def test_energy_subentry_pair_check_generic_error(
    hass: HomeAssistant,
    error: Exception,
) -> None:
    """A non-502 error while checking approval on submit re-shows the pair form as retryable."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)
    empty = AuthorizedClients(clients=[], raw=None)

    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(side_effect=[empty, error]),
        ),
        patch.object(
            TeslemetryEnergySite,
            "add_authorized_client",
            AsyncMock(return_value={}),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert not result["errors"]

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_rsa_key")
async def test_energy_subentry_empty_client_list_proceeds(
    hass: HomeAssistant,
) -> None:
    """An empty (200) authorized-client list is valid and advances to pairing."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(return_value=AuthorizedClients(clients=[], raw=None)),
        ),
        patch.object(
            TeslemetryEnergySite,
            "add_authorized_client",
            AsyncMock(return_value={}),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert not result["errors"]


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TeslaFleetError(), id="tesla_fleet_error"),
        pytest.param(_NON_502_CLIENT_RESPONSE_ERROR, id="client_response_error"),
    ],
)
async def test_energy_subentry_verify_generic_error_aborts(
    hass: HomeAssistant,
    error: Exception,
) -> None:
    """A non-502 error while listing clients aborts instead of re-registering.

    The flow can no longer read the gateway's client list, so it must not mistake
    the failure for an absent key and re-register (which would reset an already
    pending or verified key); it aborts with cannot_connect instead.
    """
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    add_client = AsyncMock(return_value={})
    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(side_effect=error),
        ),
        patch.object(TeslemetryEnergySite, "add_authorized_client", add_client),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    add_client.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_energy_subentry_resume_pending_key_not_reregistered(
    hass: HomeAssistant,
) -> None:
    """Resuming with an already-pending key advances to pairing without re-adding it."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    pending = AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key=_TEST_PUBLIC_KEY_B64,
                state=AuthorizedClientState.PENDING,
                raw={},
            )
        ],
        raw=None,
    )
    add_client = AsyncMock(return_value={})
    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(return_value=pending),
        ),
        patch.object(TeslemetryEnergySite, "add_authorized_client", add_client),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert not result["errors"]
    add_client.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_energy_subentry_verified_key_advances_to_credentials(
    hass: HomeAssistant,
) -> None:
    """An already-verified key skips registration and asks for local credentials."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    verified = AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key=_TEST_PUBLIC_KEY_B64,
                state=AuthorizedClientState.VERIFIED,
                raw={},
            )
        ],
        raw=None,
    )
    add_client = AsyncMock(return_value={})
    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(return_value=verified),
        ),
        patch.object(TeslemetryEnergySite, "add_authorized_client", add_client),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    add_client.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    ("state", "expected_error"),
    [
        pytest.param(AuthorizedClientState.PENDING, "key_pending", id="pending"),
        pytest.param(
            AuthorizedClientState.PENDING_VERIFICATION,
            "key_pending_verification",
            id="pending_verification",
        ),
    ],
)
async def test_energy_subentry_pair_submit_still_pending(
    hass: HomeAssistant,
    state: AuthorizedClientState,
    expected_error: str,
) -> None:
    """Submitting the pair form while the key is still pending re-shows it with an error."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    pending = AuthorizedClients(
        clients=[
            AuthorizedClient(public_key=_TEST_PUBLIC_KEY_B64, state=state, raw={})
        ],
        raw=None,
    )
    add_client = AsyncMock(return_value={})
    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(return_value=pending),
        ),
        patch.object(TeslemetryEnergySite, "add_authorized_client", add_client),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert not result["errors"]

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": expected_error}
    add_client.assert_not_awaited()


_UNKNOWN_CLIENT_STATES = [
    pytest.param(None, id="none"),
    pytest.param(99, id="unknown_int"),
    pytest.param("bogus", id="unknown_str"),
]


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize("state", _UNKNOWN_CLIENT_STATES)
async def test_energy_subentry_unknown_state_aborts_as_lookup_failure(
    hass: HomeAssistant,
    state: object,
) -> None:
    """An unrecognized client state aborts rather than resuming pairing.

    The typed accessor preserves a missing or unrecognized state verbatim, so a
    key in such a state cannot be reasoned about; resuming approval on it would
    leave the user working an unusable read.
    """
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    unknown = AuthorizedClients(
        clients=[
            AuthorizedClient(public_key=_TEST_PUBLIC_KEY_B64, state=state, raw={})
        ],
        raw=None,
    )
    add_client = AsyncMock(return_value={})
    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(return_value=unknown),
        ),
        patch.object(TeslemetryEnergySite, "add_authorized_client", add_client),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    add_client.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize("state", _UNKNOWN_CLIENT_STATES)
async def test_energy_subentry_pair_submit_unknown_state(
    hass: HomeAssistant,
    state: object,
) -> None:
    """An unrecognized state on submit reports a lookup failure, not pending verification.

    Reporting it as pending verification would tell the user to keep waiting for
    an approval that no longer has a readable state.
    """
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    pending = AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key=_TEST_PUBLIC_KEY_B64,
                state=AuthorizedClientState.PENDING,
                raw={},
            )
        ],
        raw=None,
    )
    unknown = AuthorizedClients(
        clients=[
            AuthorizedClient(public_key=_TEST_PUBLIC_KEY_B64, state=state, raw={})
        ],
        raw=None,
    )

    with patch.object(
        TeslemetryEnergySite,
        "find_authorized_clients",
        AsyncMock(side_effect=[pending, unknown]),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_rsa_key")
async def test_energy_subentry_pair_submit_verified_advances_to_credentials(
    hass: HomeAssistant,
) -> None:
    """Submitting the pair form once the key has become verified advances to credentials."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)

    pending = AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key=_TEST_PUBLIC_KEY_B64,
                state=AuthorizedClientState.PENDING,
                raw={},
            )
        ],
        raw=None,
    )
    verified = AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key=_TEST_PUBLIC_KEY_B64,
                state=AuthorizedClientState.VERIFIED,
                raw={},
            )
        ],
        raw=None,
    )

    with patch.object(
        TeslemetryEnergySite,
        "find_authorized_clients",
        AsyncMock(side_effect=[pending, verified]),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_energy_subentry_pair_submit_key_not_registered(
    hass: HomeAssistant,
) -> None:
    """If the key is no longer registered on the gateway, submitting the pair form errors clearly."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)
    empty = AuthorizedClients(clients=[], raw=None)

    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(return_value=empty),
        ),
        patch.object(
            TeslemetryEnergySite,
            "add_authorized_client",
            AsyncMock(return_value={}),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert not result["errors"]

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "key_not_registered"}


@pytest.mark.usefixtures("mock_rsa_key")
async def test_energy_subentry_pair_recovers_after_error(
    hass: HomeAssistant,
) -> None:
    """After a lookup error on submit, a later submit can still succeed once verified."""
    entry = await setup_platform(hass)
    subentry_id = _energy_subentry_id(entry)
    empty = AuthorizedClients(clients=[], raw=None)
    verified = AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key=_TEST_PUBLIC_KEY_B64,
                state=AuthorizedClientState.VERIFIED,
                raw={},
            )
        ],
        raw=None,
    )

    with (
        patch.object(
            TeslemetryEnergySite,
            "find_authorized_clients",
            AsyncMock(side_effect=[empty, TeslaFleetError(), verified]),
        ),
        patch.object(
            TeslemetryEnergySite,
            "add_authorized_client",
            AsyncMock(return_value={}),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert result["errors"] == {"base": "cannot_connect"}

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

"""Test yolink config flow."""

from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError
import pytest
from yolink.const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from yolink.endpoint import Endpoints
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.model import BRDP

from homeassistant.components.yolink.const import (
    AUTH_TYPE_OAUTH,
    AUTH_TYPE_UAC,
    CONF_AUTH_TYPE,
    CONF_HOME_ID,
    CONF_SECRET_KEY,
    CONF_UAID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .conftest import (
    CLIENT_ID,
    TEST_HOME_ID,
    TEST_HOME_NAME,
    TEST_SECRET_KEY,
    TEST_UAID,
    home_info_response,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


def _validation_error() -> ValidationError:
    """Return the error the library raises for a malformed API response."""
    with pytest.raises(ValidationError) as err:
        BRDP.model_validate_json("[]")
    return err.value


# Everything that leaves the home of an accepted account unknown, as the mock
# configuration of the API call the lookup makes: a request that fails with
# anything other than a refused token, and a response that names no home.
UNKNOWN_HOME_LOOKUPS = [
    pytest.param(
        {"side_effect": YoLinkClientError("-1003", "Request failed")}, id="client_error"
    ),
    pytest.param({"side_effect": TimeoutError()}, id="timeout"),
    pytest.param({"side_effect": _validation_error()}, id="validation_error"),
    pytest.param(
        {"side_effect": AttributeError("'NoneType' object has no attribute 'get'")},
        id="bug",
    ),
    pytest.param({"return_value": BRDP(code="000000")}, id="response_without_data"),
    pytest.param(
        {"return_value": BRDP(code="000000", data={"name": TEST_HOME_NAME})},
        id="response_without_id",
    ),
]


async def _async_start_uac_flow(hass: HomeAssistant) -> str:
    """Start a user flow, pick UAC from the menu and return the flow id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "uac"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "uac"
    return result["flow_id"]


async def _async_complete_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> ConfigFlowResult:
    """Run the OAuth2 flow from the menu through the token exchange."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
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
        },
    )

    return await hass.config_entries.flow.async_configure(result["flow_id"])


def _mock_oauth_entry(
    hass: HomeAssistant, data: dict[str, Any] | None = None
) -> MockConfigEntry:
    """Add an OAuth2 entry holding an outdated token to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={
            **(data or {}),
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "outdated-refresh-token",
                "access_token": "outdated-access-token",
            },
        },
    )
    entry.add_to_hass(hass)
    return entry


async def _async_complete_oauth_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    entry: MockConfigEntry,
) -> ConfigFlowResult:
    """Run the OAuth2 reauthentication of entry through the token exchange."""
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
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
        },
    )

    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("setup_credentials")
async def test_user_flow_shows_menu(hass: HomeAssistant) -> None:
    """Test the user flow offers both authentication methods."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["pick_implementation", "uac"]


@pytest.mark.parametrize(
    "entry_data",
    [
        pytest.param({CONF_AUTH_TYPE: AUTH_TYPE_OAUTH}, id="oauth_entry"),
        pytest.param({}, id="entry_without_auth_type"),
    ],
)
@pytest.mark.usefixtures("setup_credentials")
async def test_user_flow_skips_menu_with_oauth_entry(
    hass: HomeAssistant, entry_data: dict[str, str]
) -> None:
    """Test the menu is skipped when OAuth2 is already configured."""
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "uac"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_user_flow_shows_menu_with_uac_entry(hass: HomeAssistant) -> None:
    """Test a UAC entry does not prevent adding an OAuth2 entry."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_HOME_ID,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: TEST_UAID,
            CONF_SECRET_KEY: TEST_SECRET_KEY,
            CONF_HOME_ID: TEST_HOME_ID,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP


async def test_abort_if_no_configuration(hass: HomeAssistant) -> None:
    """Test picking OAuth2 without application credentials aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_pick_implementation_aborts_with_oauth_entry(
    hass: HomeAssistant,
) -> None:
    """Test picking OAuth2 aborts when an OAuth2 entry appeared meanwhile."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data={CONF_AUTH_TYPE: AUTH_TYPE_OAUTH}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_abort_if_authorization_timeout(hass: HomeAssistant) -> None:
    """Test the OAuth2 authorization timeout is handled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.LocalOAuth2Implementation.async_generate_authorize_url",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "pick_implementation"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "authorize_url_timeout"


@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_yolink_client"
)
async def test_full_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the OAuth2 flow reached through the menu."""
    assert await async_setup_component(hass, DOMAIN, {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=create"
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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "YoLink"
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"][CONF_AUTH_TYPE] == AUTH_TYPE_OAUTH
    # Recorded so the same home cannot also be added through UAC.
    assert result["data"][CONF_HOME_ID] == TEST_HOME_ID

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == DOMAIN
    assert entries[0].state is ConfigEntryState.LOADED
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_flow_uses_resolved_token_for_home_lookup(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
) -> None:
    """Test the home is looked up with the token that was just resolved."""
    result = await _async_complete_oauth_flow(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    auth_mgr = mock_yolink_client.call_args.args[0]
    assert auth_mgr.access_token() == "mock-access-token"
    mock_yolink_client.return_value.execute.assert_awaited_once_with(
        url=Endpoints.US.value.url, bsdp={"method": "Home.getGeneralInfo"}
    )


@pytest.mark.parametrize("home_lookup", UNKNOWN_HOME_LOOKUPS)
@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_flow_creates_entry_when_home_is_unknown(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
    home_lookup: dict[str, Any],
) -> None:
    """Test a home that stays unknown does not block the first entry."""
    mock_yolink_client.return_value.execute.configure_mock(**home_lookup)

    result = await _async_complete_oauth_flow(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_HOME_ID not in result["data"]


@pytest.mark.parametrize("home_lookup", UNKNOWN_HOME_LOOKUPS)
@pytest.mark.usefixtures(
    "setup_credentials",
    "current_request_with_host",
    "mock_setup_entry",
    "mock_uac_config_entry",
)
async def test_oauth_flow_aborts_when_home_is_unknown_and_entry_exists(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
    home_lookup: dict[str, Any],
) -> None:
    """Test OAuth2 is refused while the home cannot be checked for duplicates."""
    mock_yolink_client.return_value.execute.configure_mock(**home_lookup)

    result = await _async_complete_oauth_flow(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_flow_aborts_when_token_is_rejected(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
) -> None:
    """Test an account the API refuses does not become an entry."""
    mock_yolink_client.return_value.execute.side_effect = YoLinkAuthFailError(
        "000103", "Client is not exist"
    )

    result = await _async_complete_oauth_flow(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_flow_aborts_when_home_configured_by_uac(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
) -> None:
    """Test OAuth2 is refused for a home already added through UAC."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_HOME_ID,
        title=TEST_HOME_NAME,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: TEST_UAID,
            CONF_SECRET_KEY: TEST_SECRET_KEY,
            CONF_HOME_ID: TEST_HOME_ID,
        },
    ).add_to_hass(hass)

    result = await _async_complete_oauth_flow(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    "entry_data",
    [
        pytest.param({CONF_AUTH_TYPE: AUTH_TYPE_OAUTH}, id="oauth_entry"),
        pytest.param({}, id="entry_without_auth_type"),
    ],
)
@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_yolink_client"
)
async def test_oauth_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    entry_data: dict[str, str],
) -> None:
    """Test OAuth2 reauthentication is not blocked by the existing entry."""
    old_entry = _mock_oauth_entry(hass, entry_data)

    result = await _async_complete_oauth_reauth_flow(
        hass, hass_client_no_auth, aioclient_mock, old_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert old_entry.data[CONF_AUTH_TYPE] == AUTH_TYPE_OAUTH
    assert old_entry.data["token"]["access_token"] == "mock-access-token"
    assert old_entry.data["token"]["refresh_token"] == "mock-refresh-token"
    # The home of the reauthenticated account is recorded along the way.
    assert old_entry.data[CONF_HOME_ID] == TEST_HOME_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_reauthentication_updates_home_id(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
) -> None:
    """Test reauthenticating against another account records its home."""
    old_entry = _mock_oauth_entry(
        hass, {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH, CONF_HOME_ID: "home_99999"}
    )

    result = await _async_complete_oauth_reauth_flow(
        hass, hass_client_no_auth, aioclient_mock, old_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert old_entry.data[CONF_HOME_ID] == TEST_HOME_ID
    auth_mgr = mock_yolink_client.call_args.args[0]
    assert auth_mgr.access_token() == "mock-access-token"


@pytest.mark.usefixtures(
    "setup_credentials",
    "current_request_with_host",
    "mock_setup_entry",
    "mock_yolink_client",
)
async def test_oauth_reauthentication_aborts_when_home_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauthenticating into a home another entry manages is refused."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_HOME_ID,
        title=TEST_HOME_NAME,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: TEST_UAID,
            CONF_SECRET_KEY: TEST_SECRET_KEY,
            CONF_HOME_ID: TEST_HOME_ID,
        },
    ).add_to_hass(hass)
    old_entry = _mock_oauth_entry(
        hass, {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH, CONF_HOME_ID: "home_99999"}
    )

    result = await _async_complete_oauth_reauth_flow(
        hass, hass_client_no_auth, aioclient_mock, old_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert old_entry.data[CONF_HOME_ID] == "home_99999"
    assert old_entry.data["token"]["access_token"] == "outdated-access-token"


@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_reauthentication_aborts_when_token_is_rejected(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
) -> None:
    """Test an account the API refuses does not update the entry."""
    old_entry = _mock_oauth_entry(hass, {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH})
    mock_yolink_client.return_value.execute.side_effect = YoLinkAuthFailError(
        "000103", "Client is not exist"
    )

    result = await _async_complete_oauth_reauth_flow(
        hass, hass_client_no_auth, aioclient_mock, old_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_unauthorized"
    assert old_entry.data["token"]["access_token"] == "outdated-access-token"


@pytest.mark.parametrize("home_lookup", UNKNOWN_HOME_LOOKUPS)
@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_reauthentication_drops_stale_home_id(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
    home_lookup: dict[str, Any],
) -> None:
    """Test a home that stays unknown forgets the home of the previous account."""
    old_entry = _mock_oauth_entry(
        hass, {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH, CONF_HOME_ID: TEST_HOME_ID}
    )
    mock_yolink_client.return_value.execute.configure_mock(**home_lookup)

    result = await _async_complete_oauth_reauth_flow(
        hass, hass_client_no_auth, aioclient_mock, old_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # Setup records the home of the new account on the next load.
    assert CONF_HOME_ID not in old_entry.data
    assert old_entry.data["token"]["access_token"] == "mock-access-token"


@pytest.mark.parametrize("home_lookup", UNKNOWN_HOME_LOOKUPS)
@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_uac_config_entry"
)
async def test_oauth_reauthentication_aborts_when_home_is_unknown(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    home_lookup: dict[str, Any],
) -> None:
    """Test reauthentication is refused while another entry may own the home."""
    old_entry = _mock_oauth_entry(
        hass, {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH, CONF_HOME_ID: "home_99999"}
    )
    mock_yolink_client.return_value.execute.configure_mock(**home_lookup)

    result = await _async_complete_oauth_reauth_flow(
        hass, hass_client_no_auth, aioclient_mock, old_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert old_entry.data[CONF_HOME_ID] == "home_99999"
    assert old_entry.data["token"]["access_token"] == "outdated-access-token"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_uac_flow(
    hass: HomeAssistant,
    mock_yolink_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the UAC flow creates an entry keyed by home id."""
    flow_id = await _async_start_uac_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOME_NAME
    assert result["data"] == {
        CONF_AUTH_TYPE: AUTH_TYPE_UAC,
        CONF_UAID: TEST_UAID,
        CONF_SECRET_KEY: TEST_SECRET_KEY,
        CONF_HOME_ID: TEST_HOME_ID,
    }
    assert result["result"].unique_id == TEST_HOME_ID
    assert len(mock_setup_entry.mock_calls) == 1
    # Validating the credentials must not load the devices or open MQTT.
    mock_yolink_client.return_value.execute.assert_awaited_once_with(
        url=Endpoints.US.value.url, bsdp={"method": "Home.getGeneralInfo"}
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_uac_flow_unnamed_home(
    hass: HomeAssistant, mock_yolink_client: AsyncMock
) -> None:
    """Test the UAC flow falls back to a default title for an unnamed home."""
    mock_yolink_client.return_value.execute.return_value = home_info_response(name=None)

    flow_id = await _async_start_uac_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "YoLink Home"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            YoLinkAuthFailError("000103", "Invalid credentials"),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            YoLinkClientError("000201", "Connection failed"),
            "cannot_connect",
            id="client_error",
        ),
        pytest.param(TimeoutError(), "cannot_connect", id="timeout"),
        pytest.param(RuntimeError("Boom"), "unknown", id="unexpected_error"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_uac_flow_errors(
    hass: HomeAssistant,
    mock_yolink_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the UAC flow reports errors and recovers."""
    mock_yolink_client.return_value.execute.side_effect = side_effect

    flow_id = await _async_start_uac_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_yolink_client.return_value.execute.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("home_info", "error"),
    [
        pytest.param(
            BRDP(code="000000", data={"name": TEST_HOME_NAME}),
            "unknown",
            id="response_without_id",
        ),
        # A response without a payload is classified like a failed request.
        pytest.param(BRDP(code="000000"), "cannot_connect", id="response_without_data"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_uac_flow_unusable_home_info(
    hass: HomeAssistant,
    mock_yolink_client: AsyncMock,
    home_info: BRDP,
    error: str,
) -> None:
    """Test the UAC flow reports an error when no home is named."""
    mock_yolink_client.return_value.execute.return_value = home_info

    flow_id = await _async_start_uac_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.usefixtures("mock_yolink_client")
async def test_uac_flow_duplicate_home(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a second entry for the same home is rejected."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_HOME_ID,
        title=TEST_HOME_NAME,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: TEST_UAID,
            CONF_SECRET_KEY: TEST_SECRET_KEY,
            CONF_HOME_ID: TEST_HOME_ID,
        },
    ).add_to_hass(hass)

    flow_id = await _async_start_uac_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: "other-uaid", CONF_SECRET_KEY: "other-secret"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.usefixtures("mock_yolink_client", "setup_credentials")
async def test_uac_flow_aborts_when_home_configured_by_oauth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test UAC is refused for a home already added through OAuth2."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="YoLink",
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_OAUTH,
            "auth_implementation": DOMAIN,
            CONF_HOME_ID: TEST_HOME_ID,
        },
    ).add_to_hass(hass)

    # An OAuth2 entry exists, so the user flow goes straight to UAC.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.usefixtures("mock_setup_entry")
async def test_uac_flow_multiple_homes(
    hass: HomeAssistant, mock_yolink_client: AsyncMock
) -> None:
    """Test entries for different homes coexist."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="home_11111",
        title="First Home",
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: "first-uaid",
            CONF_SECRET_KEY: "first-secret",
            CONF_HOME_ID: "home_11111",
        },
    ).add_to_hass(hass)

    mock_yolink_client.return_value.execute.return_value = home_info_response(
        "home_22222", "Second Home"
    )

    flow_id = await _async_start_uac_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: "second-uaid", CONF_SECRET_KEY: "second-secret"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Second Home"
    assert result["result"].unique_id == "home_22222"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


@pytest.mark.usefixtures("mock_yolink_client")
async def test_uac_reauthentication(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test UAC reauthentication updates the credentials and reloads."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_HOME_ID,
        title=TEST_HOME_NAME,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: "old-uaid",
            CONF_SECRET_KEY: "old-secret",
        },
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "uac"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UAID: "new-uaid", CONF_SECRET_KEY: "new-secret"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert old_entry.data == {
        CONF_AUTH_TYPE: AUTH_TYPE_UAC,
        CONF_UAID: "new-uaid",
        CONF_SECRET_KEY: "new-secret",
        CONF_HOME_ID: TEST_HOME_ID,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_uac_reauthentication_wrong_home(
    hass: HomeAssistant, mock_yolink_client: AsyncMock
) -> None:
    """Test UAC reauthentication with credentials for another home."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_HOME_ID,
        title=TEST_HOME_NAME,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: "old-uaid",
            CONF_SECRET_KEY: "old-secret",
            CONF_HOME_ID: TEST_HOME_ID,
        },
    )
    old_entry.add_to_hass(hass)

    mock_yolink_client.return_value.execute.return_value = home_info_response(
        "home_99999", "Other Home"
    )

    result = await old_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UAID: "other-uaid", CONF_SECRET_KEY: "other-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert old_entry.data[CONF_UAID] == "old-uaid"

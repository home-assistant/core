"""Test yolink config flow."""

from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
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

HOME_LOOKUP_FAILURES = [
    pytest.param(
        {"side_effect": YoLinkAuthFailError("000103", "Client is not exist")},
        "oauth_unauthorized",
        id="auth_failed",
    ),
    pytest.param(
        {"side_effect": YoLinkClientError("-1003", "Request failed")},
        "cannot_connect",
        id="client_error",
    ),
    pytest.param({"side_effect": TimeoutError()}, "cannot_connect", id="timeout"),
    pytest.param(
        {"side_effect": AttributeError("'NoneType' object has no attribute 'get'")},
        "unknown",
        id="unexpected_error",
    ),
    pytest.param(
        {"return_value": BRDP(code="000000")},
        "cannot_connect",
        id="response_without_data",
    ),
    pytest.param(
        {"return_value": BRDP(code="000000", data={"name": TEST_HOME_NAME})},
        "cannot_connect",
        id="response_without_id",
    ),
]


OAUTH_TOKEN = {
    "refresh_token": "mock-refresh-token",
    "access_token": "mock-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


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


async def _async_finish_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
) -> ConfigFlowResult:
    """Follow the authorization callback of a flow and exchange the code."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(OAUTH2_TOKEN, json=OAUTH_TOKEN)

    return await hass.config_entries.flow.async_configure(flow_id)


async def _async_pick_oauth(hass: HomeAssistant) -> str:
    """Start a user flow, pick OAuth2 from the menu and return the flow id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    return result["flow_id"]


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


async def _async_complete_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> ConfigFlowResult:
    """Run the OAuth2 flow from the menu through the token exchange."""
    flow_id = await _async_pick_oauth(hass)
    return await _async_finish_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, flow_id
    )


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

    return await _async_finish_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"]
    )


@pytest.mark.usefixtures("setup_credentials", "mock_config_entry")
async def test_user_flow_skips_menu_with_oauth_entry(hass: HomeAssistant) -> None:
    """Test the menu is skipped when OAuth2 is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "uac"


@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_uac_config_entry"
)
async def test_user_flow_shows_menu_with_uac_entry(hass: HomeAssistant) -> None:
    """Test a UAC entry does not prevent adding an OAuth2 entry."""
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


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_full_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_yolink_client: AsyncMock,
) -> None:
    """Test the OAuth2 flow reached through the menu."""
    assert await async_setup_component(hass, DOMAIN, {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["pick_implementation", "uac"]

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

    aioclient_mock.post(OAUTH2_TOKEN, json=OAUTH_TOKEN)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "YoLink"
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"][CONF_AUTH_TYPE] == AUTH_TYPE_OAUTH
    assert result["data"][CONF_HOME_ID] == TEST_HOME_ID

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == OAUTH_TOKEN

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == DOMAIN
    assert entries[0].state is ConfigEntryState.LOADED
    assert len(mock_setup_entry.mock_calls) == 1

    auth_mgr = mock_yolink_client.call_args.args[0]
    assert auth_mgr.access_token() == "mock-access-token"
    mock_yolink_client.return_value.execute.assert_awaited_once_with(
        url=Endpoints.US.value.url, bsdp={"method": "Home.getGeneralInfo"}
    )


@pytest.mark.parametrize(("home_lookup", "reason"), HOME_LOOKUP_FAILURES)
@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_flow_aborts_when_home_lookup_fails(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
    home_lookup: dict[str, Any],
    reason: str,
) -> None:
    """Test an account whose home cannot be determined does not become an entry."""
    mock_yolink_client.return_value.execute.configure_mock(**home_lookup)

    result = await _async_complete_oauth_flow(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_oauth_flow_aborts_when_oauth_entry_exists(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
) -> None:
    """Test OAuth2 is refused when an OAuth2 entry appeared during the flow."""
    flow_id = await _async_pick_oauth(hass)
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN).add_to_hass(hass)

    result = await _async_finish_oauth_flow(
        hass, hass_client_no_auth, aioclient_mock, flow_id
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_yolink_client.return_value.execute.assert_not_awaited()


@pytest.mark.usefixtures(
    "setup_credentials",
    "current_request_with_host",
    "mock_setup_entry",
    "mock_yolink_client",
    "mock_uac_config_entry",
)
async def test_oauth_flow_aborts_when_home_configured_by_uac(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test OAuth2 is refused for a home already added through UAC."""
    result = await _async_complete_oauth_flow(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    "entry_data",
    [
        pytest.param({CONF_AUTH_TYPE: AUTH_TYPE_OAUTH}, id="oauth_entry"),
        pytest.param({}, id="entry_without_auth_type"),
        pytest.param(
            {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH, CONF_HOME_ID: "home_99999"},
            id="entry_of_other_home",
        ),
        pytest.param(
            {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH, CONF_HOME_ID: TEST_HOME_ID},
            id="entry_of_same_home",
        ),
    ],
)
@pytest.mark.usefixtures("setup_credentials", "current_request_with_host")
async def test_oauth_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_yolink_client: AsyncMock,
    entry_data: dict[str, str],
) -> None:
    """Test OAuth2 reauthentication updates the token and the home."""
    old_entry = _mock_oauth_entry(hass, entry_data)

    result = await _async_complete_oauth_reauth_flow(
        hass, hass_client_no_auth, aioclient_mock, old_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert old_entry.data[CONF_AUTH_TYPE] == AUTH_TYPE_OAUTH
    assert old_entry.data["token"]["access_token"] == "mock-access-token"
    assert old_entry.data["token"]["refresh_token"] == "mock-refresh-token"
    assert old_entry.data[CONF_HOME_ID] == TEST_HOME_ID
    assert len(mock_setup_entry.mock_calls) == 1
    auth_mgr = mock_yolink_client.call_args.args[0]
    assert auth_mgr.access_token() == "mock-access-token"


@pytest.mark.usefixtures(
    "setup_credentials",
    "current_request_with_host",
    "mock_setup_entry",
    "mock_yolink_client",
    "mock_uac_config_entry",
)
async def test_oauth_reauthentication_aborts_when_home_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauthenticating into a home another entry manages is refused."""
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


@pytest.mark.parametrize(("home_lookup", "reason"), HOME_LOOKUP_FAILURES)
@pytest.mark.usefixtures(
    "setup_credentials", "current_request_with_host", "mock_setup_entry"
)
async def test_oauth_reauthentication_aborts_when_home_lookup_fails(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_yolink_client: AsyncMock,
    home_lookup: dict[str, Any],
    reason: str,
) -> None:
    """Test an account whose home cannot be determined does not update the entry."""
    old_entry = _mock_oauth_entry(
        hass, {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH, CONF_HOME_ID: "home_99999"}
    )
    data_before = dict(old_entry.data)
    mock_yolink_client.return_value.execute.configure_mock(**home_lookup)

    result = await _async_complete_oauth_reauth_flow(
        hass, hass_client_no_auth, aioclient_mock, old_entry
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert old_entry.data == data_before


@pytest.mark.parametrize(
    ("home_info", "title"),
    [
        pytest.param(home_info_response(), TEST_HOME_NAME, id="named_home"),
        pytest.param(
            BRDP(code="000000", data={"id": TEST_HOME_ID}),
            "YoLink Home",
            id="unnamed_home",
        ),
    ],
)
async def test_uac_flow(
    hass: HomeAssistant,
    mock_yolink_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    home_info: BRDP,
    title: str,
) -> None:
    """Test the UAC flow creates an entry keyed by home id."""
    mock_yolink_client.return_value.execute.return_value = home_info

    flow_id = await _async_start_uac_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
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


@pytest.mark.parametrize(
    ("home_lookup", "error"),
    [
        pytest.param(
            {"side_effect": YoLinkAuthFailError("000103", "Invalid credentials")},
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            {"side_effect": YoLinkClientError("000201", "Connection failed")},
            "cannot_connect",
            id="client_error",
        ),
        pytest.param({"side_effect": TimeoutError()}, "cannot_connect", id="timeout"),
        pytest.param(
            {"side_effect": RuntimeError("Boom")}, "unknown", id="unexpected_error"
        ),
        pytest.param(
            {"return_value": BRDP(code="000000")},
            "cannot_connect",
            id="response_without_data",
        ),
        pytest.param(
            {"return_value": BRDP(code="000000", data={"name": TEST_HOME_NAME})},
            "cannot_connect",
            id="response_without_id",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_uac_flow_errors(
    hass: HomeAssistant,
    mock_yolink_client: AsyncMock,
    home_lookup: dict[str, Any],
    error: str,
) -> None:
    """Test the UAC flow reports errors and recovers."""
    execute = mock_yolink_client.return_value.execute
    execute.configure_mock(**home_lookup)

    flow_id = await _async_start_uac_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    execute.configure_mock(side_effect=None, return_value=home_info_response())
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_HOME_ID


@pytest.mark.usefixtures("mock_yolink_client", "mock_uac_config_entry")
async def test_uac_flow_duplicate_home(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a second entry for the same home is rejected."""
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


@pytest.mark.usefixtures("mock_setup_entry", "mock_uac_config_entry")
async def test_uac_flow_multiple_homes(
    hass: HomeAssistant, mock_yolink_client: AsyncMock
) -> None:
    """Test entries for different homes coexist."""
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
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test UAC reauthentication updates the credentials and reloads."""
    result = await mock_uac_config_entry.start_reauth_flow(hass)
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
    assert mock_uac_config_entry.data == {
        CONF_AUTH_TYPE: AUTH_TYPE_UAC,
        CONF_UAID: "new-uaid",
        CONF_SECRET_KEY: "new-secret",
        CONF_HOME_ID: TEST_HOME_ID,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_uac_reauthentication_wrong_home(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_yolink_client: AsyncMock,
) -> None:
    """Test UAC reauthentication with credentials for another home."""
    mock_yolink_client.return_value.execute.return_value = home_info_response(
        "home_99999", "Other Home"
    )

    result = await mock_uac_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UAID: "other-uaid", CONF_SECRET_KEY: "other-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_uac_config_entry.data[CONF_UAID] == TEST_UAID

"""Test yolink config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yolink.const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant import config_entries, setup
from homeassistant.components import application_credentials
from homeassistant.components.yolink.const import (
    AUTH_TYPE_OAUTH,
    AUTH_TYPE_UAC,
    CONF_AUTH_TYPE,
    CONF_HOME_ID,
    CONF_SECRET_KEY,
    CONF_UAID,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "12345"
CLIENT_SECRET = "6789"
DOMAIN = "yolink"

# UAC test credentials
TEST_UAID = "test-uaid-12345"
TEST_SECRET_KEY = "test-secret-key-6789"
TEST_HOME_ID = "home_12345"
TEST_HOME_NAME = "My Test Home"


async def test_user_flow_shows_menu(
    hass: HomeAssistant,
) -> None:
    """Check that user flow shows menu."""
    await setup.async_setup_component(hass, DOMAIN, {})
    await application_credentials.async_import_client_credential(
        hass,
        DOMAIN,
        application_credentials.ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert "pick_implementation" in result["menu_options"]
    assert "uac" in result["menu_options"]


async def test_abort_if_no_configuration(hass: HomeAssistant) -> None:
    """Check flow abort when no configuration and selecting OAuth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Menu is shown first even without credentials
    assert result["type"] is FlowResultType.MENU

    # When selecting OAuth without credentials, it should abort
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_alongside_uac_entries(hass: HomeAssistant) -> None:
    """Check that OAuth entries and UAC entries can coexist."""
    await setup.async_setup_component(hass, DOMAIN, {})
    await application_credentials.async_import_client_credential(
        hass,
        DOMAIN,
        application_credentials.ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )
    # Add a UAC entry first
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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Menu should still be shown - UAC entry doesn't block OAuth
    assert result["type"] is FlowResultType.MENU

    # Selecting OAuth should proceed to the external step (not abort)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )
    # Should show external step for OAuth (since only one implementation)
    assert result["type"] is FlowResultType.EXTERNAL_STEP


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_duplicate_entry_blocked(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check that duplicate OAuth entries are prevented."""
    await setup.async_setup_component(hass, DOMAIN, {})
    await application_credentials.async_import_client_credential(
        hass,
        DOMAIN,
        application_credentials.ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )
    # Add existing OAuth entry
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,  # OAuth uses DOMAIN as unique_id
        data={CONF_AUTH_TYPE: AUTH_TYPE_OAUTH},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Menu is still shown
    assert result["type"] is FlowResultType.MENU

    # Select OAuth from menu
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_implementation"}
    )
    # External step proceeds (duplicate check happens after OAuth)
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    # Complete OAuth flow
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "scope": "create",
        },
    )

    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    # Now the duplicate check should abort
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_oauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full OAuth flow via menu."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {},
    )
    await application_credentials.async_import_client_credential(
        hass,
        DOMAIN,
        application_credentials.ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    # Select OAuth
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

    with (
        patch("homeassistant.components.yolink.api.ConfigEntryAuth"),
        patch(
            "homeassistant.components.yolink.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"][CONF_AUTH_TYPE] == AUTH_TYPE_OAUTH

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }

    assert DOMAIN in hass.config.components
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_uac_flow_success(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Check successful UAC flow."""
    await setup.async_setup_component(hass, DOMAIN, {})

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    # Select UAC
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "uac"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "uac"

    # Enter credentials
    with patch(
        "homeassistant.components.yolink.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOME_NAME
    assert result["data"] == {
        CONF_AUTH_TYPE: AUTH_TYPE_UAC,
        CONF_UAID: TEST_UAID,
        CONF_SECRET_KEY: TEST_SECRET_KEY,
        CONF_HOME_ID: TEST_HOME_ID,
    }


async def test_uac_flow_invalid_auth(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Check UAC flow with invalid credentials."""
    await setup.async_setup_component(hass, DOMAIN, {})

    # Make the mock raise auth error
    mock_yolink_home_config_flow.return_value.async_setup.side_effect = (
        YoLinkAuthFailError("000103", "Invalid credentials")
    )

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "uac"}
    )

    # Enter bad credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UAID: "bad-uaid", CONF_SECRET_KEY: "bad-secret"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_uac_flow_cannot_connect(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Check UAC flow with connection error."""
    await setup.async_setup_component(hass, DOMAIN, {})

    # Make the mock raise connection error
    mock_yolink_home_config_flow.return_value.async_setup.side_effect = (
        YoLinkClientError("000201", "Connection failed")
    )

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "uac"}
    )

    # Enter credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_uac_flow_timeout(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Check UAC flow with timeout error."""
    await setup.async_setup_component(hass, DOMAIN, {})

    # Make the mock raise timeout error
    mock_yolink_home_config_flow.return_value.async_setup.side_effect = TimeoutError()

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "uac"}
    )

    # Enter credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_uac_flow_unknown_error(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Check UAC flow with unknown error."""
    await setup.async_setup_component(hass, DOMAIN, {})

    # Make the mock raise unexpected error
    mock_yolink_home_config_flow.return_value.async_setup.side_effect = RuntimeError(
        "Unexpected"
    )

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "uac"}
    )

    # Enter credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UAID: TEST_UAID, CONF_SECRET_KEY: TEST_SECRET_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_multiple_uac_entries_different_homes(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Check that multiple UAC entries for different homes are allowed."""
    await setup.async_setup_component(hass, DOMAIN, {})

    # Add first UAC entry
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

    # Set up mock for second home
    mock_home_info = MagicMock()
    mock_home_info.data = {"id": "home_22222", "name": "Second Home"}
    mock_yolink_home_config_flow.return_value.async_get_home_info.return_value = (
        mock_home_info
    )

    # Start the flow for second home
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "uac"}
    )

    # Enter credentials for second home
    with patch(
        "homeassistant.components.yolink.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_UAID: "second-uaid", CONF_SECRET_KEY: "second-secret"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Second Home"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_uac_flow_duplicate_home(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Check that duplicate UAC entries for same home are prevented."""
    await setup.async_setup_component(hass, DOMAIN, {})

    # Add existing UAC entry
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

    # Try to add same home again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "uac"}
    )

    # Enter credentials for same home
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UAID: "new-uaid", CONF_SECRET_KEY: "new-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_abort_if_authorization_timeout(hass: HomeAssistant) -> None:
    """Check yolink authorization timeout."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {},
    )
    await application_credentials.async_import_client_credential(
        hass,
        DOMAIN,
        application_credentials.ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test yolink OAuth reauthentication."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {},
    )

    await application_credentials.async_import_client_credential(
        hass,
        DOMAIN,
        application_credentials.ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        version=1,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_OAUTH,
            "refresh_token": "outdated_fresh_token",
            "access_token": "outdated_access_token",
        },
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

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

    with (
        patch("homeassistant.components.yolink.api.ConfigEntryAuth"),
        patch(
            "homeassistant.components.yolink.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    token_data = old_entry.data["token"]
    assert token_data["access_token"] == "mock-access-token"
    assert token_data["refresh_token"] == "mock-refresh-token"
    assert token_data["type"] == "Bearer"
    assert token_data["expires_in"] == 60
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup.mock_calls) == 1


async def test_uac_reauthentication(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Test yolink UAC reauthentication."""
    await setup.async_setup_component(hass, DOMAIN, {})

    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_HOME_ID,
        version=1,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: "old-uaid",
            CONF_SECRET_KEY: "old-secret",
            CONF_HOME_ID: TEST_HOME_ID,
        },
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    # Confirm reauth
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "uac"

    # Enter new credentials
    with patch(
        "homeassistant.components.yolink.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_UAID: "new-uaid", CONF_SECRET_KEY: "new-secret"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert old_entry.data[CONF_UAID] == "new-uaid"
    assert old_entry.data[CONF_SECRET_KEY] == "new-secret"


async def test_uac_reauthentication_wrong_account(
    hass: HomeAssistant,
    mock_yolink_home_config_flow: AsyncMock,
) -> None:
    """Test yolink UAC reauthentication with wrong account."""
    await setup.async_setup_component(hass, DOMAIN, {})

    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_HOME_ID,
        version=1,
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: "old-uaid",
            CONF_SECRET_KEY: "old-secret",
            CONF_HOME_ID: TEST_HOME_ID,
        },
    )
    old_entry.add_to_hass(hass)

    # Set up mock to return different home_id
    mock_home_info = MagicMock()
    mock_home_info.data = {"id": "different_home_id", "name": "Different Home"}
    mock_yolink_home_config_flow.return_value.async_get_home_info.return_value = (
        mock_home_info
    )

    result = await old_entry.start_reauth_flow(hass)

    flows = hass.config_entries.flow.async_progress()
    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

    # Enter credentials for different home
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_UAID: "different-uaid", CONF_SECRET_KEY: "different-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"

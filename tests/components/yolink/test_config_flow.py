"""Test yolink config flow."""
import asyncio
from http import HTTPStatus
from unittest.mock import patch

from yolink.const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components import application_credentials
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry

CLIENT_ID = "12345"
CLIENT_SECRET = "6789"
DOMAIN = "yolink"


async def test_abort_if_no_configuration(hass):
    """Check flow abort when no configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


async def test_abort_if_existing_entry(hass: HomeAssistant):
    """Check flow abort when an entry already exist."""
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow(
    hass, hass_client_no_auth, aioclient_mock, current_request_with_host
):
    """Check full flow."""
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
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
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

    with patch("homeassistant.components.yolink.api.ConfigEntryAuth"), patch(
        "homeassistant.components.yolink.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["auth_implementation"] == DOMAIN

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }

    assert DOMAIN in hass.config.components
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is config_entries.ConfigEntryState.LOADED

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_abort_if_authorization_timeout(hass, current_request_with_host):
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
    with patch(
        "homeassistant.components.yolink.config_entry_oauth2_flow."
        "LocalOAuth2Implementation.async_generate_authorize_url",
        side_effect=asyncio.TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "authorize_url_timeout"


async def test_reauthentication(
    hass, hass_client_no_auth, aioclient_mock, current_request_with_host
):
    """Test yolink reauthentication."""
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
            "refresh_token": "outdated_fresh_token",
            "access_token": "outdated_access_token",
        },
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": old_entry.unique_id,
            "entry_id": old_entry.entry_id,
        },
        data=old_entry.data,
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})

    # pylint: disable=protected-access
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

    with patch("homeassistant.components.yolink.api.ConfigEntryAuth"):
        with patch(
            "homeassistant.components.yolink.async_setup_entry", return_value=True
        ) as mock_setup:
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
    token_data = old_entry.data["token"]
    assert token_data["access_token"] == "mock-access-token"
    assert token_data["refresh_token"] == "mock-refresh-token"
    assert token_data["type"] == "Bearer"
    assert token_data["expires_in"] == 60
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup.mock_calls) == 1

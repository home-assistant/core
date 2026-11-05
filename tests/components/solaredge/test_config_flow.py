"""Tests for the SolarEdge config flow."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL

from homeassistant.components.recorder import Recorder
from homeassistant.components.solaredge.const import (
    CONF_SITE_ID,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_CALLBACK_PATH,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SITE_ID, TOKEN


async def _complete_oauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
    authorize_url: str,
) -> dict:
    """Complete the external OAuth callback."""
    client = await hass_client_no_auth()
    response = await client.get(URL(authorize_url).path_qs, allow_redirects=False)
    assert response.status == 302
    assert response.headers["Location"].startswith(f"{OAUTH2_AUTHORIZE}?")
    assert "scope=SITE_DATA+DEVICE_DATA" in response.headers["Location"]
    assert "access_duration=24" in response.headers["Location"]
    assert "code_challenge=" in response.headers["Location"]
    assert "code_challenge_method=S256" in response.headers["Location"]
    cookie = response.cookies[f"solaredge_oauth_{flow_id}"]
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            **TOKEN,
            "token_type": "Bearer",
        },
    )
    response = await client.get(
        f"{OAUTH2_CALLBACK_PATH}?code=code&site_id={SITE_ID}",
        headers={"Cookie": f"{cookie.key}={cookie.value}"},
    )
    assert response.status == 200
    return await hass.config_entries.flow.async_configure(flow_id)


async def test_full_flow(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    solaredge_api: AsyncMock,
) -> None:
    """Test OAuth setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SITE_ID: SITE_ID}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"].startswith(
        "https://example.com/api/solaredge/oauth/authorize?flow_id="
    )

    result = await _complete_oauth(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        result["url"],
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SITE_ID
    assert result["result"].data[CONF_SITE_ID] == SITE_ID
    assert result["result"].data[CONF_TOKEN]["refresh_token"] == "refresh-token"
    assert aioclient_mock.mock_calls[-1][2]["code_verifier"]


async def test_site_not_active(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    solaredge_api: AsyncMock,
) -> None:
    """Test an inactive site is rejected."""
    solaredge_api.get_details.return_value = {
        "details": {"status": "Disabled", "name": "Home"}
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SITE_ID: SITE_ID}
    )
    result = await _complete_oauth(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        result["url"],
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "site_not_active"


async def test_callback_requires_authorizing_browser(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
    setup_credentials: None,
) -> None:
    """Test a callback cannot consume a flow started in another browser."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SITE_ID: SITE_ID}
    )
    authorizing_client = await hass_client_no_auth()
    response = await authorizing_client.get(
        URL(result["url"]).path_qs, allow_redirects=False
    )
    assert response.status == 302

    other_client = await hass_client_no_auth()
    response = await other_client.get(
        f"{OAUTH2_CALLBACK_PATH}?code=code&site_id={SITE_ID}"
    )
    assert response.status == 400
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_invalid_code_does_not_consume_pending_flow(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    setup_credentials: None,
) -> None:
    """Test a rejected code can be retried without restarting the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SITE_ID: SITE_ID}
    )
    client = await hass_client_no_auth()
    response = await client.get(URL(result["url"]).path_qs, allow_redirects=False)
    assert response.status == 302
    cookie = response.cookies[f"solaredge_oauth_{result['flow_id']}"]
    aioclient_mock.post(OAUTH2_TOKEN, status=400, json={"error": "invalid_grant"})

    response = await client.get(
        f"{OAUTH2_CALLBACK_PATH}?code=invalid&site_id={SITE_ID}",
        headers={"Cookie": f"{cookie.key}={cookie.value}"},
    )
    assert response.status == 400
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_reauth_migrates_api_key_entry(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    solaredge_api: AsyncMock,
) -> None:
    """Test OAuth reauth removes the retired API key and keeps the site ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        unique_id=SITE_ID,
        data={CONF_SITE_ID: SITE_ID, CONF_API_KEY: "retired-api-key"},
        version=2,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    result = await _complete_oauth(
        hass,
        hass_client_no_auth,
        aioclient_mock,
        result["flow_id"],
        result["url"],
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert CONF_API_KEY not in entry.data
    assert entry.data[CONF_SITE_ID] == SITE_ID
    assert entry.data[CONF_TOKEN]["refresh_token"] == "refresh-token"


async def test_reconfigure_keeps_oauth_token(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure does not replace OAuth data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        unique_id=SITE_ID,
        data={
            CONF_SITE_ID: SITE_ID,
            "auth_implementation": DOMAIN,
            CONF_TOKEN: TOKEN,
        },
        version=2,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_TOKEN] == TOKEN


async def test_migration_starts_reauth(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test a V1 API-key entry is migrated and requests OAuth reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        unique_id=None,
        data={CONF_SITE_ID: SITE_ID, CONF_API_KEY: "retired-api-key"},
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.unique_id == SITE_ID
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH

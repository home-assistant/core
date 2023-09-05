"""Tests for config flow."""
from http import HTTPStatus
from unittest.mock import patch

from aiohttp.test_utils import TestClient

from homeassistant.components.withings.const import (
    CONF_PROFILE,
    CONF_USE_WEBHOOK,
    DOMAIN,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_EXTERNAL_URL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import AUTH_CALLBACK_PATH
from homeassistant.setup import async_setup_component

from .conftest import CLIENT_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://account.withings.com/oauth2_user/authorize2?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
        "&scope=user.info,user.metrics,user.activity,user.sleepevents"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://wbsapi.withings.net/v2/oauth2",
        json={
            "body": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "userid": 600,
            },
        },
    )
    with patch(
        "homeassistant.components.withings.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "profile"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PROFILE: "Henk"}
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Henk"
    assert "result" in result
    assert result["result"].unique_id == "600"
    assert "token" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"


async def test_config_non_unique_profile(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    current_request_with_host: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup a non-unique profile."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_PROFILE: "Henk"}, unique_id="0"
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://account.withings.com/oauth2_user/authorize2?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
        "&scope=user.info,user.metrics,user.activity,user.sleepevents"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://wbsapi.withings.net/v2/oauth2",
        json={
            "body": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "userid": 10,
            },
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "profile"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PROFILE: "Henk"}
    )

    assert result
    assert result["errors"]["base"] == "already_configured"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PROFILE: "Henk 2"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Henk 2"
    assert "result" in result
    assert result["result"].unique_id == "10"


async def test_config_reauth_profile(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Test reauth an existing profile re-creates the config entry."""
    hass_config = {
        HA_DOMAIN: {
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_EXTERNAL_URL: "http://127.0.0.1:8080/",
        },
        DOMAIN: {
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_client_secret",
            CONF_USE_WEBHOOK: False,
        },
    }
    await async_process_ha_core_config(hass, hass_config.get(HA_DOMAIN))
    assert await async_setup_component(hass, DOMAIN, hass_config)
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_PROFILE: "person0"}, unique_id="0"
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "title_placeholders": {"name": config_entry.title},
            "unique_id": config_entry.unique_id,
        },
        data={"profile": "person0"},
    )
    assert result
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {CONF_PROFILE: "person0"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client: TestClient = await hass_client_no_auth()
    resp = await client.get(f"{AUTH_CALLBACK_PATH}?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://wbsapi.withings.net/v2/oauth2",
        json={
            "body": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "userid": "0",
            },
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert entries[0].data["token"]["refresh_token"] == "mock-refresh-token"

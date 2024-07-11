"""Tests for config flow."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from monzopy import AuthorisationExpiredError
import pytest

from homeassistant.components.monzo.application_credentials import (
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.components.monzo.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import setup_integration
from .conftest import CLIENT_ID, USER_ID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
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

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}/?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "user_id": "600",
        },
    )
    with patch(
        "homeassistant.components.monzo.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert len(mock_setup.mock_calls) == 0

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "await_approval_confirmation"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"confirm": True}
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert "result" in result
    assert result["result"].unique_id == "600"
    assert "token" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_non_unique_profile(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup a non-unique profile."""
    await setup_integration(hass, polling_config_entry)
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

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}/?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "user_id": str(USER_ID),
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_reauth_profile(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
) -> None:
    """Test reauth an existing profile reauthenticates the config entry."""
    await setup_integration(hass, polling_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": polling_config_entry.entry_id,
        },
        data=polling_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}/?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "new-mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "user_id": str(USER_ID),
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "await_approval_confirmation"
    assert polling_config_entry.data["token"]["access_token"] == "mock-access-token"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"confirm": True}
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert polling_config_entry.data["token"]["access_token"] == "new-mock-access-token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_reauth_wrong_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test reauth with wrong account."""
    await setup_integration(hass, polling_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": polling_config_entry.entry_id,
        },
        data=polling_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}/?"
        f"response_type=code&client_id={CLIENT_ID}&"
        "redirect_uri=https://example.com/auth/external/callback&"
        f"state={state}"
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
            "user_id": 12346,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_api_can_trigger_reauth(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauth an existing profile reauthenticates the config entry."""
    await setup_integration(hass, polling_config_entry)

    monzo.user_account.accounts.side_effect = AuthorisationExpiredError()
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == SOURCE_REAUTH

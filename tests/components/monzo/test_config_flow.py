"""Tests for config flow."""

import asyncio
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError
from monzopy import AuthorisationExpiredError
import pytest

from homeassistant.components.monzo.application_credentials import (
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.components.monzo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import setup_integration
from .conftest import CLIENT_ID, USER_ID

from tests.common import MockConfigEntry
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
    approval_granted = asyncio.Event()
    check_count = 0

    async def check_approval() -> list[dict]:
        nonlocal check_count
        check_count += 1
        if check_count == 1:
            raise AuthorisationExpiredError
        await approval_granted.wait()
        return []

    approval_api = AsyncMock()
    approval_api.user_account.accounts.side_effect = check_approval
    with (
        patch(
            "homeassistant.components.monzo.async_setup_entry", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.monzo.config_flow.async_generate_id",
            return_value="generated-webhook-id",
        ),
        patch(
            "homeassistant.components.monzo.config_flow.MonzoAPI",
            return_value=approval_api,
        ),
        patch("homeassistant.components.monzo.config_flow.asyncio.sleep", AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert len(mock_setup.mock_calls) == 0

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "wait_for_approval"
        assert result["progress_action"] == "wait_for_approval"

        approval_granted.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert "result" in result
    assert result["result"].unique_id == "600"
    assert "token" in result["result"].data
    assert result["result"].data["token"]["access_token"] == "mock-access-token"
    assert result["result"].data["token"]["refresh_token"] == "mock-refresh-token"
    assert result["result"].data[CONF_WEBHOOK_ID] == "generated-webhook-id"


@pytest.mark.parametrize(
    ("approval_error", "step_id"),
    [
        pytest.param(TimeoutError(), "approval_timeout", id="timeout"),
        pytest.param(
            ClientConnectionError(), "connection_error", id="connection-error"
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_approval_error_retry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    approval_error: Exception,
    step_id: str,
) -> None:
    """Test retrying after checking approval fails."""
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
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

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
    approval_checked = asyncio.Event()

    async def fail_approval_check() -> None:
        await approval_checked.wait()
        raise approval_error

    approval_granted = asyncio.Event()

    async def approve() -> None:
        await approval_granted.wait()

    with (
        patch("homeassistant.components.monzo.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.monzo.config_flow.MonzoFlowHandler._async_wait_for_approval",
            side_effect=fail_approval_check,
        ) as approval_check,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        approval_checked.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == step_id

        approval_check.side_effect = approve
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        approval_granted.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    result = await polling_config_entry.start_reauth_flow(hass)
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

    approval_granted = asyncio.Event()

    async def check_approval() -> list[dict]:
        await approval_granted.wait()
        return []

    approval_api = AsyncMock()
    approval_api.user_account.accounts.side_effect = check_approval
    with patch(
        "homeassistant.components.monzo.config_flow.MonzoAPI",
        return_value=approval_api,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "wait_for_approval"
        assert polling_config_entry.data["token"]["access_token"] == (
            "mock-access-token"
        )

        approval_granted.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

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

    result = await polling_config_entry.start_reauth_flow(hass)
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
            "user_id": "12346",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"

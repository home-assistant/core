"""Tests for the SmartThings config flow module."""

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.smartthings import OLD_DATA
from homeassistant.components.smartthings.const import (
    CONF_INSTALLED_APP_ID,
    CONF_LOCATION_ID,
    CONF_REFRESH_TOKEN,
    CONF_SUBSCRIPTION_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture
def use_cloud(hass: HomeAssistant) -> None:
    """Set up the cloud component."""
    hass.config.components.add("cloud")


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Check a full flow."""
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
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+sse+r:installedapps+"
        "w:installedapps"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    result["data"]["token"].pop("expires_at")
    assert result["data"][CONF_TOKEN] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "token_type": "Bearer",
        "expires_in": 82806,
        "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
        "r:locations:* w:locations:* x:locations:* "
        "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
        "access_tier": 0,
        "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
    }
    assert result["result"].unique_id == "397678e5-9995-4a39-9d9f-ae6ba310236c"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_not_enough_scopes(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we abort if we don't have enough scopes."""
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
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+sse+r:installedapps+"
        "w:installedapps"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* "
            "r:installedapps w:installedapps",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_scopes"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_duplicate_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate entry is not able to set up."""
    mock_config_entry.add_to_hass(hass)
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
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+sse+r:installedapps+"
        "w:installedapps"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_cloud(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Check we abort when cloud is not enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cloud_not_enabled"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

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
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* sse w:rules:*",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_config_entry.data["token"].pop("expires_at")
    assert mock_config_entry.data[CONF_TOKEN] == {
        "refresh_token": "new-refresh-token",
        "access_token": "new-access-token",
        "token_type": "Bearer",
        "expires_in": 82806,
        "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
        "r:locations:* w:locations:* x:locations:* "
        "r:scenes:* x:scenes:* r:rules:* sse w:rules:*",
        "access_tier": 0,
        "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
    }


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_reauthentication_wrong_scopes(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with wrong scopes."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

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
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* "
            "r:installedapps w:installedapps",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_scopes"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with different account."""
    mock_config_entry.add_to_hass(hass)

    mock_smartthings.get_locations.return_value[
        0
    ].location_id = "123123123-2be1-4e40-b257-e4ef59083324"

    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

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
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauthentication_no_cloud(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication without cloud."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cloud_not_enabled"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_migration(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_old_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with different account."""
    mock_old_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_old_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_old_config_entry.state is ConfigEntryState.SETUP_ERROR

    result = hass.config_entries.flow.async_progress()[0]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

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
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_old_config_entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.flow.async_progress()) == 0
    mock_old_config_entry.data[CONF_TOKEN].pop("expires_at")
    assert mock_old_config_entry.data == {
        "auth_implementation": DOMAIN,
        "old_data": {
            CONF_ACCESS_TOKEN: "mock-access-token",
            CONF_REFRESH_TOKEN: "mock-refresh-token",
            CONF_CLIENT_ID: "CLIENT_ID",
            CONF_CLIENT_SECRET: "CLIENT_SECRET",
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123aa123-2be1-4e40-b257-e4ef59083324",
        },
        CONF_TOKEN: {
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
        CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
        CONF_SUBSCRIPTION_ID: "f5768ce8-c9e5-4507-9020-912c0c60e0ab",
    }
    assert mock_old_config_entry.unique_id == "397678e5-9995-4a39-9d9f-ae6ba310236c"
    assert mock_old_config_entry.version == 3
    assert mock_old_config_entry.minor_version == 2


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_migration_wrong_location(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_old_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with wrong location."""
    mock_old_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_old_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_old_config_entry.state is ConfigEntryState.SETUP_ERROR

    mock_smartthings.get_locations.return_value[
        0
    ].location_id = "123123123-2be1-4e40-b257-e4ef59083324"

    result = hass.config_entries.flow.async_progress()[0]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

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
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_location_mismatch"
    assert mock_old_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_old_config_entry.data == {
        OLD_DATA: {
            CONF_ACCESS_TOKEN: "mock-access-token",
            CONF_REFRESH_TOKEN: "mock-refresh-token",
            CONF_CLIENT_ID: "CLIENT_ID",
            CONF_CLIENT_SECRET: "CLIENT_SECRET",
            CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
            CONF_INSTALLED_APP_ID: "123aa123-2be1-4e40-b257-e4ef59083324",
        }
    }
    assert (
        mock_old_config_entry.unique_id
        == "appid123-2be1-4e40-b257-e4ef59083324_397678e5-9995-4a39-9d9f-ae6ba310236c"
    )
    assert mock_old_config_entry.version == 3
    assert mock_old_config_entry.minor_version == 2


@pytest.mark.usefixtures("current_request_with_host")
async def test_migration_no_cloud(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_old_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with different account."""
    mock_old_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_old_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_old_config_entry.state is ConfigEntryState.SETUP_ERROR

    result = hass.config_entries.flow.async_progress()[0]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cloud_not_enabled"

"""Test the OneDrive config flow."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

from onedrive_personal_sdk.exceptions import OneDriveException
from onedrive_personal_sdk.models.items import Drive
import pytest

from homeassistant import config_entries
from homeassistant.components.onedrive_for_business.const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_PATH,
    CONF_TENANT_ID,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import setup_integration
from .const import CLIENT_ID, TENANT_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def _do_get_token(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    scope = "Files.ReadWrite.All+offline_access+openid"
    authorize_url = OAUTH2_AUTHORIZE.format(tenant_id=TENANT_ID)
    token_url = OAUTH2_TOKEN.format(tenant_id=TENANT_ID)

    assert result["url"] == (
        f"{authorize_url}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={scope}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        token_url,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_onedrive_client_init: MagicMock,
) -> None:
    """Check full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_tenant"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TENANT_ID: TENANT_ID}
    )
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Ensure the token callback is set up correctly
    token_callback = mock_onedrive_client_init.call_args[0][0]
    assert await token_callback() == "mock-access-token"

    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATH: "myFolder"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["title"] == "John Doe's OneDrive"
    assert result["result"].unique_id == "mock_drive_id"
    assert result["data"][CONF_TOKEN][CONF_ACCESS_TOKEN] == "mock-access-token"
    assert result["data"][CONF_TOKEN]["refresh_token"] == "mock-refresh-token"
    assert result["data"][CONF_FOLDER_PATH] == "myFolder"
    assert result["data"][CONF_FOLDER_ID] == "my_folder_id"


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow_with_owner_not_found(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_onedrive_client: MagicMock,
    mock_approot: MagicMock,
) -> None:
    """Ensure we get a default title if the drive's owner can't be read."""

    mock_approot.created_by.user = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_tenant"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TENANT_ID: TENANT_ID}
    )
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATH: "myFolder"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["title"] == "OneDrive"
    assert result["result"].unique_id == "mock_drive_id"
    assert result["data"][CONF_TOKEN][CONF_ACCESS_TOKEN] == "mock-access-token"
    assert result["data"][CONF_TOKEN]["refresh_token"] == "mock-refresh-token"
    assert result["data"][CONF_FOLDER_PATH] == "myFolder"
    assert result["data"][CONF_FOLDER_ID] == "my_folder_id"

    mock_onedrive_client.reset_mock()


@pytest.mark.usefixtures("current_request_with_host")
async def test_error_during_folder_creation(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_onedrive_client: MagicMock,
) -> None:
    """Ensure we can create the backup folder."""

    mock_onedrive_client.create_folder.side_effect = OneDriveException()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_tenant"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TENANT_ID: TENANT_ID}
    )
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATH: "myFolder"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "folder_creation_error"}

    mock_onedrive_client.create_folder.side_effect = None

    # clear error and try again
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATH: "myFolder"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "John Doe's OneDrive"
    assert result["result"].unique_id == "mock_drive_id"
    assert result["data"][CONF_TOKEN][CONF_ACCESS_TOKEN] == "mock-access-token"
    assert result["data"][CONF_TOKEN]["refresh_token"] == "mock-refresh-token"
    assert result["data"][CONF_FOLDER_PATH] == "myFolder"
    assert result["data"][CONF_FOLDER_ID] == "my_folder_id"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (Exception, "unknown"),
        (OneDriveException, "connection_error"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_onedrive_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test errors during flow."""

    mock_onedrive_client.get_approot.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_tenant"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TENANT_ID: TENANT_ID}
    )
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test already configured account."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_tenant"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TENANT_ID: TENANT_ID}
    )
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure flow."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_folder"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATH: "new/folder/path"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_FOLDER_PATH] == "new/folder/path"
    assert mock_config_entry.data[CONF_FOLDER_ID] == "my_folder_id"
    assert mock_config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN] == "mock-access-token"
    assert mock_config_entry.data[CONF_TOKEN]["refresh_token"] == "mock-refresh-token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reconfigure_flow_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_onedrive_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure flow errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_folder"

    mock_onedrive_client.create_folder.side_effect = OneDriveException()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATH: "new/folder/path"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_folder"
    assert result["errors"] == {"base": "folder_creation_error"}

    # clear side effect and try again
    mock_onedrive_client.create_folder.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATH: "new/folder/path"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_FOLDER_PATH] == "new/folder/path"
    assert mock_config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN] == "mock-access-token"
    assert mock_config_entry.data[CONF_TOKEN]["refresh_token"] == "mock-refresh-token"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reconfigure_flow_wrong_drive(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_drive: Drive,
) -> None:
    """Test that the reconfigure flow fails on a different drive id."""
    mock_drive.id = "other_drive_id"

    mock_config_entry.add_to_hass(hass)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the reauth flow works."""

    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN] == "mock-access-token"
    assert mock_config_entry.data[CONF_TOKEN]["refresh_token"] == "mock-refresh-token"
    assert mock_config_entry.data[CONF_FOLDER_PATH] == "backups/home_assistant"
    assert mock_config_entry.data[CONF_FOLDER_ID] == "my_folder_id"
    assert mock_config_entry.data[CONF_TENANT_ID] == TENANT_ID


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow_id_changed(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_drive: Drive,
) -> None:
    """Test that the reauth flow fails on a different drive id."""

    await setup_integration(hass, mock_config_entry)

    mock_drive.id = "other_drive_id"

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await _do_get_token(hass, result, hass_client_no_auth, aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_drive"
    assert mock_config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN] == "mock-access-token"
    assert mock_config_entry.data[CONF_TOKEN]["refresh_token"] == "mock-refresh-token"
    assert mock_config_entry.data[CONF_FOLDER_PATH] == "backups/home_assistant"
    assert mock_config_entry.data[CONF_FOLDER_ID] == "my_folder_id"
    assert mock_config_entry.data[CONF_TENANT_ID] == TENANT_ID

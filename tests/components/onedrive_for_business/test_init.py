"""Test the OneDrive setup."""

from copy import copy
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)
from onedrive_personal_sdk.models.items import Folder
import pytest

from homeassistant.components.onedrive_for_business.const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_PATH,
    CONF_TENANT_ID,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client_init: MagicMock,
    mock_onedrive_client: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    # Ensure the token callback is set up correctly
    token_callback = mock_onedrive_client_init.call_args[0][0]
    assert await token_callback() == "mock-access-token"

    # make sure metadata migration is not called
    assert mock_onedrive_client.upload_file.call_count == 0
    assert mock_onedrive_client.update_drive_item.call_count == 0

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("status", "state", "reason", "reauth_expected"),
    [
        pytest.param(
            HTTPStatus.BAD_REQUEST,
            ConfigEntryState.SETUP_ERROR,
            "Authentication failed",
            True,
            id="reauth",
        ),
        pytest.param(
            HTTPStatus.TOO_MANY_REQUESTS,
            ConfigEntryState.SETUP_RETRY,
            "Failed to connect to OneDrive",
            False,
            id="transient",
        ),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
            "Failed to connect to OneDrive",
            False,
            id="server_error",
        ),
    ],
)
@pytest.mark.parametrize("expires_at", [0], ids=["expired"])
async def test_token_refresh_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    state: ConfigEntryState,
    reason: str,
    reauth_expected: bool,
) -> None:
    """Test a failing token refresh during setup."""
    aioclient_mock.post(
        OAUTH2_TOKEN.format(tenant_id=mock_config_entry.data[CONF_TENANT_ID]),
        status=status,
        json={},
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state
    assert mock_config_entry.reason == reason
    assert bool(hass.config_entries.flow.async_progress()) is reauth_expected


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        (AuthenticationError(403, "Auth failed"), ConfigEntryState.SETUP_ERROR),
        (OneDriveException(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_approot_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test errors during approot retrieval."""
    mock_onedrive_client.get_drive_item.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_get_integration_folder_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    mock_folder: Folder,
) -> None:
    """Test faulty integration folder creation."""
    folder_name = copy(mock_config_entry.data[CONF_FOLDER_PATH])
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_onedrive_client.create_folder.assert_called_once_with(
        parent_id="root",
        name=folder_name,
    )
    # ensure the folder id and name are updated
    assert mock_config_entry.data[CONF_FOLDER_ID] == mock_folder.id
    assert mock_config_entry.data[CONF_FOLDER_PATH] == folder_name


async def test_get_integration_folder_creation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_onedrive_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test faulty integration folder creation error."""
    mock_onedrive_client.get_drive_item.side_effect = NotFoundError(404, "Not found")
    mock_onedrive_client.create_folder.side_effect = OneDriveException()
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Failed to get backups/home_assistant folder" in caplog.text


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.onedrive_for_business.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

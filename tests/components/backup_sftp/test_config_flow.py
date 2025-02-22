"""Tests config_flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied
import pytest

from homeassistant.components.backup_sftp.const import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryError

from .conftest import TEST_AGENT_ID

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 22,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PRIVATE_KEY_FILE: "private_key",
    CONF_BACKUP_LOCATION: "backup_location",
}


@pytest.mark.usefixtures("current_request_with_host")
async def test_backup_sftp_full_flow(
    hass: HomeAssistant,
) -> None:
    """Test the full backup_sftp config flow with valid user input."""
    # Start the configuration flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # The first step should be the "user" form.
    assert result["step_id"] == "user"

    # Prepare a fake BackupAgentClient to simulate a successful connection.
    fake_client = AsyncMock()
    fake_client.__aenter__.return_value = fake_client
    fake_client.list_backup_location.return_value = []  # Simulate a successful directory check.
    fake_client.get_identifier = MagicMock(return_value=TEST_AGENT_ID)

    # Patch the BackupAgentClient so that when the flow creates it, our fake is used.
    with patch(
        "homeassistant.components.backup_sftp.config_flow.BackupAgentClient",
        return_value=fake_client,
    ) as mock_client:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_client.mock_calls) == 1

    # Verify that a new config entry is created.
    assert result["type"] == FlowResultType.CREATE_ENTRY
    expected_title = f"SFTP Backup - {USER_INPUT[CONF_USERNAME]}@{USER_INPUT[CONF_HOST]}:{USER_INPUT[CONF_PORT]}"
    assert result["title"] == expected_title
    assert result["data"] == USER_INPUT


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test successful failure of already added config entry."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception_type", "error_base"),
    [
        (OSError, "os_error"),
        (PermissionDenied, "permission_denied"),
        (SFTPNoSuchFile, "sftp_no_such_file"),
        (SFTPPermissionDenied, "sftp_permission_denied"),
        (ConfigEntryError, "config_entry_error"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
@patch("homeassistant.components.backup_sftp.config_flow.BackupAgentClient")
async def test_config_flow_exceptions(
    backup_agent_client: MagicMock,
    exception_type: Exception,
    error_base: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    async_cm_mock: AsyncMock,
) -> None:
    """Test successful failure of already added config entry."""

    async def add():
        config_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()
        return result

    backup_agent_client.return_value = async_cm_mock

    async_cm_mock.list_backup_location = AsyncMock(
        side_effect=exception_type("Error message")
    )
    result = await add()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] and result["errors"]["base"] == error_base

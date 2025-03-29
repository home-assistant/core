"""Tests config_flow."""

from collections.abc import Awaitable, Callable, Generator
from tempfile import NamedTemporaryFile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied
import pytest

from homeassistant.components.backup_sftp.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryError

from .conftest import USER_INPUT

from tests.common import MockConfigEntry

type ComponentSetup = Callable[[], Awaitable[None]]


@pytest.fixture
def mock_connect(
    fake_connect: AsyncMock,
) -> Generator[tuple[MagicMock, MagicMock, dict[str, Any]]]:
    """Fixture that yields mocked connect and SSHClientConnectionOptions objects."""

    with (
        patch(
            "homeassistant.components.backup_sftp.config_flow.connect",
            return_value=fake_connect,
        ) as _mock_connect,
        patch(
            "homeassistant.components.backup_sftp.config_flow.SSHClientConnectionOptions",
            return_value=MagicMock(),
        ) as _mock_ssh_client_options,
        NamedTemporaryFile() as tmpfile,
    ):
        user_input = USER_INPUT.copy()
        user_input[CONF_PRIVATE_KEY_FILE] = tmpfile.name
        yield (_mock_connect, _mock_ssh_client_options, user_input)


@pytest.mark.usefixtures("current_request_with_host")
async def test_backup_sftp_full_flow(
    hass: HomeAssistant,
    mock_connect: tuple[MagicMock, MagicMock, dict[str, Any]],
) -> None:
    """Test the full backup_sftp config flow with valid user input."""

    mock_client, _, user_input = mock_connect
    # Start the configuration flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # The first step should be the "user" form.
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_client.mock_calls) == 1

    # Verify that a new config entry is created.
    assert result["type"] == FlowResultType.CREATE_ENTRY
    expected_title = f"{user_input[CONF_USERNAME]}@{user_input[CONF_HOST]}"
    assert result["title"] == expected_title
    assert result["data"] == user_input


@pytest.mark.usefixtures("current_request_with_host")
async def test_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_connect: tuple[MagicMock, MagicMock, dict[str, Any]],
) -> None:
    """Test successful failure of already added config entry."""
    _, _, user_input = mock_connect
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
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
async def test_config_flow_exceptions(
    exception_type: Exception,
    error_base: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_connect: tuple[MagicMock, MagicMock, dict[str, Any]],
) -> None:
    """Test successful failure of already added config entry."""

    mock_client, _, user_input = mock_connect
    mock_client.side_effect = exception_type("Error message.")

    # config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] and result["errors"]["base"] == error_base

    # Recover from the error
    mock_client.side_effect = None

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("new_password", "new_host", "reauth_reason"),
    [
        ("new1234new", USER_INPUT[CONF_HOST], "reauth_successful"),
        (USER_INPUT[CONF_PASSWORD], "newhost", "reauth_key_changes"),
    ],
    ids=["successful_change", "key_change_made"],
)
@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth(
    new_password: str,
    new_host: str,
    reauth_reason: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_connect: tuple[MagicMock, MagicMock, dict[str, Any]],
) -> None:
    """Test the reauthentication flow."""

    _, _, user_input = mock_connect
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    user_input[CONF_HOST] = new_host
    user_input[CONF_PASSWORD] = new_password
    user_input[CONF_PRIVATE_KEY_FILE] = ""
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reauth_reason
    assert result["description_placeholders"] is None


@pytest.mark.usefixtures("current_request_with_host")
async def test_config_entry_error(hass: HomeAssistant) -> None:
    """Test config flow with raised `ConfigEntryError`."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert "errors" in result and result["errors"]["base"] == "config_entry_error"
    assert (
        "description_placeholders" in result
        and "error_message" in result["description_placeholders"]
        and "Private key file not found in provided path:"
        in result["description_placeholders"]["error_message"]
    )

    user_input = USER_INPUT.copy()
    user_input[CONF_PASSWORD] = ""
    user_input[CONF_PRIVATE_KEY_FILE] = ""

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert "errors" in result and result["errors"]["base"] == "config_entry_error"
    assert (
        "description_placeholders" in result
        and "error_message" in result["description_placeholders"]
        and "Please configure password or private key"
        in result["description_placeholders"]["error_message"]
    )

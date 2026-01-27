"""Tests config_flow."""

from collections.abc import Awaitable, Callable
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from asyncssh import KeyImportError, generate_private_key
from asyncssh.misc import PermissionDenied
from asyncssh.sftp import SFTPNoSuchFile, SFTPPermissionDenied
import pytest

from homeassistant.components.sftp_storage.config_flow import (
    SFTPStorageInvalidPrivateKey,
    SFTPStorageMissingPasswordOrPkey,
)
from homeassistant.components.sftp_storage.const import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import USER_INPUT, SSHClientConnectionMock

from tests.common import MockConfigEntry

type ComponentSetup = Callable[[], Awaitable[None]]


@pytest.fixture
def mock_process_uploaded_file():
    """Mocks ability to process uploaded private key."""
    with (
        patch(
            "homeassistant.components.sftp_storage.config_flow.process_uploaded_file"
        ) as mock_process_uploaded_file,
        patch("shutil.move") as mock_shutil_move,
        NamedTemporaryFile() as f,
    ):
        pkey = generate_private_key("ssh-rsa")
        f.write(pkey.export_private_key("pkcs8-pem"))
        f.flush()
        mock_process_uploaded_file.return_value.__enter__.return_value = f.name
        mock_shutil_move.return_value = f.name
        yield


@pytest.mark.xdist_group("sftp_storage")
@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_process_uploaded_file")
async def test_backup_sftp_full_flow(
    hass: HomeAssistant,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test the full backup_sftp config flow with valid user input."""

    user_input = USER_INPUT.copy()
    mock_ssh_connection._sftp._mock_getcwd = user_input[CONF_BACKUP_LOCATION]
    # Start the configuration flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # The first step should be the "user" form.
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    # Verify that a new config entry is created.
    assert result["type"] is FlowResultType.CREATE_ENTRY
    expected_title = f"{user_input[CONF_USERNAME]}@{user_input[CONF_HOST]}"
    assert result["title"] == expected_title

    # Make sure to match the `private_key_file` from entry
    user_input[CONF_PRIVATE_KEY_FILE] = result["data"][CONF_PRIVATE_KEY_FILE]

    assert result["data"] == user_input


@pytest.mark.xdist_group("sftp_storage")
@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_process_uploaded_file")
@pytest.mark.usefixtures("mock_ssh_connection")
async def test_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.xdist_group("sftp_storage")
@pytest.mark.parametrize(
    ("exception_type", "backup_location", "error_base"),
    [
        (OSError, None, "os_error"),
        (SFTPStorageInvalidPrivateKey, None, "invalid_key"),
        (PermissionDenied, None, "permission_denied"),
        (SFTPStorageMissingPasswordOrPkey, None, "key_or_password_needed"),
        (SFTPNoSuchFile, None, "sftp_no_such_file"),
        (SFTPPermissionDenied, None, "sftp_permission_denied"),
        (SFTPPermissionDenied, "/backup/location", "sftp_write_permission_denied"),
        (SFTPPermissionDenied, "/", "sftp_write_root_permission_denied"),
        (Exception, None, "unknown"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_process_uploaded_file")
async def test_config_flow_exceptions(
    exception_type: type[Exception],
    backup_location: str | None,
    error_base: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ssh_connection: SSHClientConnectionMock,
) -> None:
    """Test successful failure of already added config entry."""

    user_input = USER_INPUT.copy()
    if exception_type == SFTPPermissionDenied and backup_location is not None:
        mock_target = mock_ssh_connection._sftp._mock_unlink
        user_input[CONF_BACKUP_LOCATION] = backup_location
    else:
        mock_target = mock_ssh_connection._sftp._mock_chdir
    mock_target.side_effect = exception_type("Error message.")

    # config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] and result["errors"]["base"] == error_base

    # Recover from the error
    mock_ssh_connection._sftp._mock_chdir.side_effect = None

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.xdist_group("sftp_storage")
@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.usefixtures("mock_process_uploaded_file")
async def test_config_entry_error(hass: HomeAssistant) -> None:
    """Test config flow with raised `KeyImportError`."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.sftp_storage.config_flow.SSHClientConnectionOptions",
            side_effect=KeyImportError("Invalid key"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert "errors" in result and result["errors"]["base"] == "invalid_key"

    user_input = USER_INPUT.copy()
    user_input[CONF_PASSWORD] = ""
    del user_input[CONF_PRIVATE_KEY_FILE]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert "errors" in result and result["errors"]["base"] == "key_or_password_needed"

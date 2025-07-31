"""Tests for SFTP Storage."""

from unittest.mock import patch

from asyncssh.sftp import SFTPPermissionDenied
import pytest

from homeassistant.components.sftp_storage import SFTPConfigEntryData
from homeassistant.components.sftp_storage.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .asyncssh_mock import SSHClientConnectionMock
from .conftest import USER_INPUT, ComponentSetup


@pytest.mark.usefixtures("mock_ssh_connection")
async def test_setup_and_unload(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test successful setup and unload."""

    # Patch the `exists` function of Path so that we can also
    # test the `homeassistant.components.sftp_storage.client.get_client_keys()` function
    with (
        patch(
            "homeassistant.components.sftp_storage.client.SSHClientConnectionOptions"
        ),
        patch("pathlib.Path.exists", return_value=True),
    ):
        await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert entries[0].state is ConfigEntryState.NOT_LOADED
    assert f"Unloading integration: {entries[0].unique_id}" in caplog.messages


async def test_setup_error(
    mock_ssh_connection: SSHClientConnectionMock,
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test setup error."""
    mock_ssh_connection._sftp._mock_chdir.side_effect = SFTPPermissionDenied(
        "Error message"
    )
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR


async def test_setup_unexpected_error(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup error."""
    with patch(
        "homeassistant.components.sftp_storage.client.connect",
        side_effect=OSError("Error message"),
    ):
        await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR
    assert (
        "Failure while attempting to establish SSH connection. Please check SSH credentials and if changed, re-install the integration"
        in caplog.text
    )


async def test_async_remove_entry(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test async_remove_entry."""
    await setup_integration()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    config_entry = entries[0]
    with patch("shutil.rmtree") as rmtree_mock:
        assert await hass.config_entries.async_remove(config_entry.entry_id)
        assert rmtree_mock.call_count == 1

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception_raised"),
    [
        OSError(
            "Error message"
        ),  # Base error for `FileNotFoundError`, `NotADirectoryError` and Per`missionError.
        TypeError("Error message"),  # Can be called internally by `lstat`, `open`.
        ValueError("Error message"),  # Can be called internally by `lstat`, `open`.
        NotImplementedError(
            "Error message"
        ),  # Due to misuse of `dir_fd` on an unsupported platform.
    ],
)
async def test_async_remove_entry_exceptions(
    exception_raised: Exception,
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_remove_entry with possible exceptions that could be raised by `rmtree`."""
    await setup_integration()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    config_entry = entries[0]
    with patch("shutil.rmtree", side_effect=exception_raised) as rmtree_mock:
        assert await hass.config_entries.async_remove(config_entry.entry_id)
        assert rmtree_mock.call_count == 1

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert f"Removed storage directory for {config_entry.unique_id}" in caplog.messages


async def test_config_entry_data_password_hidden() -> None:
    """Test hiding password in `SFTPConfigEntryData` string representation."""
    user_input = USER_INPUT.copy()
    entry_data = SFTPConfigEntryData(**user_input)
    assert "password=" not in str(entry_data)

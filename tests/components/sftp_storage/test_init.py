"""Tests for SFTP Storage."""

from pathlib import Path
from unittest.mock import patch

from asyncssh.sftp import SFTPPermissionDenied
import pytest

from homeassistant.components.sftp_storage import SFTPConfigEntryData
from homeassistant.components.sftp_storage.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.ulid import ulid

from .asyncssh_mock import SSHClientConnectionMock
from .conftest import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    USER_INPUT,
    ComponentSetup,
    private_key_file,
)

from tests.common import MockConfigEntry


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

    assert entries[0].state is ConfigEntryState.NOT_LOADED
    assert (
        f"Unloading {DOMAIN} integration for host {entries[0].data[CONF_USERNAME]}@{entries[0].data[CONF_HOST]}"
        in caplog.messages
    )


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
    # Setup default config entry
    await setup_integration()

    # Setup additional config entry
    agent_id = ulid()
    with private_key_file(hass) as private_key:
        new_config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id=agent_id,
            unique_id=agent_id,
            title="another@192.168.0.100",
            data={
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 22,
                CONF_USERNAME: "another",
                CONF_PASSWORD: "password",
                CONF_PRIVATE_KEY_FILE: str(private_key),
                CONF_BACKUP_LOCATION: "backup_location",
            },
        )
        new_config_entry.add_to_hass(hass)
        await setup_integration(new_config_entry)
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 2

        config_entry = entries[0]
        private_key = Path(config_entry.data[CONF_PRIVATE_KEY_FILE])
        new_private_key = Path(new_config_entry.data[CONF_PRIVATE_KEY_FILE])

        # Make sure private keys from both configs exists
        assert private_key.parent == new_private_key.parent
        assert private_key.exists()
        assert new_private_key.exists()

        # Remove first config entry - the private key from second will still be in filesystem
        # as well as integration storage directory
        assert await hass.config_entries.async_remove(config_entry.entry_id)
        assert not private_key.exists()
        assert new_private_key.exists()
        assert new_private_key.parent.exists()
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        # Remove the second config entry, ensuring all files and integration storage directory removed.
        assert await hass.config_entries.async_remove(new_config_entry.entry_id)
        assert not new_private_key.exists()
        assert not new_private_key.parent.exists()

        assert hass.config_entries.async_entries(DOMAIN) == []
        assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("patch_target", "expected_logs"),
    [
        (
            "os.unlink",
            [
                "Failed to remove private key",
                f"Storage directory for {DOMAIN} integration is not empty",
            ],
        ),
        ("os.rmdir", ["Error occurred while removing directory"]),
    ],
)
async def test_async_remove_entry_errors(
    patch_target: str,
    expected_logs: list[str],
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_remove_entry."""
    # Setup default config entry
    await setup_integration()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    config_entry = entries[0]

    with patch(patch_target, side_effect=OSError(13, "Permission denied")):
        await hass.config_entries.async_remove(config_entry.entry_id)
        for logline in expected_logs:
            assert logline in caplog.text


async def test_config_entry_data_password_hidden() -> None:
    """Test hiding password in `SFTPConfigEntryData` string representation."""
    user_input = USER_INPUT.copy()
    entry_data = SFTPConfigEntryData(**user_input)
    assert "password=" not in str(entry_data)

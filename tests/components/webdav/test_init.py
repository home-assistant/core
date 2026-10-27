"""Test WebDAV component setup."""

from unittest.mock import AsyncMock

from aiowebdav2.exceptions import (
    AccessDeniedError,
    ConnectionExceptionError,
    NoConnectionError,
    UnauthorizedError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.webdav.const import CONF_BACKUP_PATH, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.parametrize(
    ("error", "expected_message", "expected_state"),
    [
        (
            UnauthorizedError("Unauthorized"),
            "Invalid username or password",
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            AccessDeniedError("/access_denied"),
            "Access denied to /access_denied",
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ConnectionExceptionError(ConnectionError("Connection refused")),
            "Connection refused",
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            NoConnectionError("webdav.demo"),
            "No connection with webdav.demo",
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            TimeoutError(),
            "",
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=[
        "UnauthorizedError",
        "AccessDeniedError",
        "ConnectionExceptionError",
        "NoConnectionError",
        "TimeoutError",
    ],
)
async def test_error_during_setup(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    expected_message: str,
    expected_state: ConfigEntryState,
) -> None:
    """Test handling of various errors during setup."""
    webdav_client.check.side_effect = error

    config_entry = MockConfigEntry(
        title="user@webdav.demo",
        domain=DOMAIN,
        data={
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
            CONF_BACKUP_PATH: "/backups",
        },
        entry_id="01JKXV07ASC62D620DGYNG2R8H",
    )
    await setup_integration(hass, config_entry)

    assert expected_message in caplog.text
    assert config_entry.state is expected_state


async def test_auth_error_during_setup_starts_reauth(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    webdav_client.check.side_effect = UnauthorizedError("https://webdav.demo")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("check_side_effect", "mkdir_side_effect", "expected_message"),
    [
        pytest.param(
            [False],
            None,
            "Cannot access or create backup path",
            id="root_check_failed",
        ),
        pytest.param(
            [True, NoConnectionError("webdav.demo")],
            None,
            "No connection with webdav.demo",
            id="check_no_connection",
        ),
        pytest.param(
            [True, False],
            ConnectionExceptionError(ConnectionError("Connection refused")),
            "Connection refused",
            id="mkdir_connection_exception",
        ),
        pytest.param(
            [True, False],
            TimeoutError(),
            "",
            id="mkdir_timeout",
        ),
        pytest.param(
            [True, False],
            [False],
            "Cannot access or create backup path",
            id="mkdir_failed",
        ),
    ],
)
async def test_backup_path_error_during_setup(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    check_side_effect: list[bool | Exception],
    mkdir_side_effect: Exception | list[bool] | None,
    expected_message: str,
) -> None:
    """Test errors while ensuring the backup path exists are retried."""
    webdav_client.check.side_effect = check_side_effect
    webdav_client.mkdir.side_effect = mkdir_side_effect

    config_entry = MockConfigEntry(
        title="user@webdav.demo",
        domain=DOMAIN,
        data={
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
            CONF_BACKUP_PATH: "/backups",
        },
        entry_id="01JKXV07ASC62D620DGYNG2R8H",
    )
    await setup_integration(hass, config_entry)

    assert expected_message in caplog.text
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_with_root_backup_path(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the default root backup path only checks the server root."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    webdav_client.check.assert_awaited_once_with()
    webdav_client.mkdir.assert_not_called()

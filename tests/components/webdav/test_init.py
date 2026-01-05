"""Test WebDAV component setup."""

from unittest.mock import AsyncMock

from aiowebdav2.exceptions import AccessDeniedError, UnauthorizedError
import pytest

from homeassistant.components.webdav.const import CONF_BACKUP_PATH, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


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
    ],
    ids=["UnauthorizedError", "AccessDeniedError"],
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

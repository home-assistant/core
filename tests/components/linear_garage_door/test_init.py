"""Test Nice G.O. init."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from nice_go import ApiError, AuthFailedError
import pytest

from homeassistant.components.linear_garage_door.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import setup_integration

from tests.common import MockConfigEntry


async def test_unload_entry(
    hass: HomeAssistant, mock_nice_go: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the unload entry."""

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "entry_state"),
    [
        (
            AuthFailedError(),
            ConfigEntryState.SETUP_ERROR,
        ),
        (ApiError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test reauth trigger setup."""

    mock_nice_go.authenticate_refresh.side_effect = side_effect

    await setup_integration(hass, mock_config_entry, [])
    assert mock_config_entry.state == entry_state


async def test_migrate_entry(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the migrate entry."""

    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            "email": "test-email",
            "password": "test-password",
            "site_id": "test-site-id",
            "device_id": "test-device-id",
        },
        title="test-site-id",
        version=1,
    )

    await setup_integration(hass, mock_config_entry, [])

    assert mock_config_entry.version == 2
    assert mock_config_entry.data == {
        "email": "test-email",
        "password": "test-password",
        "refresh_token": "test-refresh-token",
        "refresh_token_creation_time": freezer.time_to_freeze.timestamp(),
    }
    assert mock_nice_go.authenticate.call_count == 1


async def test_migrate_entry_auth_failed(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the migrate entry with authentication failure."""

    mock_nice_go.authenticate.side_effect = AuthFailedError()

    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            "email": "test-email",
            "password": "test-password",
            "site_id": "test-site-id",
            "device_id": "test-device-id",
        },
        title="test-site-id",
        version=1,
    )

    await setup_integration(hass, mock_config_entry, [])

    assert mock_config_entry.version == 1
    assert mock_config_entry.data == {
        "email": "test-email",
        "password": "test-password",
        "site_id": "test-site-id",
        "device_id": "test-device-id",
    }
    assert mock_nice_go.authenticate.call_count == 1


async def test_migrate_entry_user_nonexistent(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the migrate entry with user nonexistent."""

    err = ApiError()
    err.__context__ = Exception("UserNotFoundException")
    mock_nice_go.authenticate.side_effect = err

    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            "email": "test-email",
            "password": "test-password",
            "site_id": "test-site-id",
            "device_id": "test-device-id",
        },
        title="test-site-id",
        version=1,
    )

    await setup_integration(hass, mock_config_entry, [])

    assert mock_config_entry.version == 1
    assert mock_config_entry.data == {
        "email": "test-email",
        "password": "test-password",
        "site_id": "test-site-id",
        "device_id": "test-device-id",
    }
    assert mock_nice_go.authenticate.call_count == 1

    issue = issue_registry.async_get_issue(
        DOMAIN, f"account_migration_required_{DOMAIN}"
    )

    assert issue
    assert issue.domain == DOMAIN

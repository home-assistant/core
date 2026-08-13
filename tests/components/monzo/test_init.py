"""Tests for component initialisation."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from monzopy import AuthorisationExpiredError
import pytest

from homeassistant.components.monzo.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration
from .conftest import TEST_ACCOUNTS, TITLE, USER_ID

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_config_entry_title_uses_authenticated_owner(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
) -> None:
    """Test the config entry is named after the authenticated owner."""
    monzo.user_account.accounts.return_value = [
        {
            **TEST_ACCOUNTS[0],
            "owners": [
                {
                    "user_id": "another-user",
                    "preferred_name": "Jane Martin",
                },
                {
                    "user_id": str(USER_ID),
                    "preferred_name": "Jake Martin",
                    "preferred_first_name": "Jake",
                },
            ],
        },
        TEST_ACCOUNTS[1],
    ]

    await setup_integration(hass, polling_config_entry)

    assert polling_config_entry.title == "Jake Martin"


async def test_config_entry_title_falls_back_without_owner(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
) -> None:
    """Test the existing title is retained without matching owner metadata."""
    await setup_integration(hass, polling_config_entry)

    assert polling_config_entry.title == TITLE


async def test_api_can_trigger_reauth(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauth an existing profile reauthenticates the config entry."""
    await setup_integration(hass, polling_config_entry)

    monzo.user_account.accounts.side_effect = AuthorisationExpiredError()
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize(
    ("minor_version", "unique_id"),
    [
        pytest.param(1, 600, id="minor-version-1"),
        pytest.param(2, "600", id="minor-version-2"),
    ],
)
async def test_migrate_entry(
    hass: HomeAssistant, minor_version: int, unique_id: int | str
) -> None:
    """Test migrating an older config entry to 1.3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "user_id": "600",
            },
        },
        version=1,
        minor_version=minor_version,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.monzo.async_generate_id",
            return_value="generated-webhook-id",
        ),
        patch("homeassistant.components.monzo.async_setup_entry", return_value=True),
        patch("homeassistant.components.monzo.async_unload_entry", return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 1
        assert entry.minor_version == 3
        assert entry.unique_id == "600"
        assert entry.data[CONF_WEBHOOK_ID] == "generated-webhook-id"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    polling_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.monzo.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(polling_config_entry.entry_id)
        await hass.async_block_till_done()

    assert polling_config_entry.state is ConfigEntryState.SETUP_RETRY

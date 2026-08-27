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
from homeassistant.helpers import device_registry as dr
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
    polling_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(polling_config_entry, title=DOMAIN)

    assert await hass.config_entries.async_setup(polling_config_entry.entry_id)

    assert polling_config_entry.title == "Jake Martin"


async def test_config_entry_title_falls_back_without_owner(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
) -> None:
    """Test the existing title is retained without matching owner metadata."""
    monzo.user_account.accounts.return_value = [
        {key: value for key, value in account.items() if key != "owners"}
        for account in TEST_ACCOUNTS
    ]
    polling_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(polling_config_entry, title=DOMAIN)

    assert await hass.config_entries.async_setup(polling_config_entry.entry_id)

    assert polling_config_entry.title == DOMAIN


async def test_config_entry_title_preserves_custom_name(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
) -> None:
    """Test a user-defined config entry title is retained."""
    await setup_integration(hass, polling_config_entry)

    assert polling_config_entry.title == TITLE


async def test_device_names(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test devices use descriptive resource names."""
    joint_account = {
        **TEST_ACCOUNTS[0],
        "id": "acc_joint",
        "name": "Joint Account",
        "owners": [
            TEST_ACCOUNTS[0]["owners"][0],
            {
                "user_id": "another-user",
                "preferred_name": "Jane Martin",
                "preferred_first_name": "Jane",
            },
        ],
    }
    monzo.user_account.accounts.return_value = [TEST_ACCOUNTS[0], joint_account]
    monzo.user_account.pots.return_value = [
        {
            "id": "pot_joint",
            "name": "Holiday",
            "balance": 12345,
            "currency": "GBP",
        }
    ]

    await setup_integration(hass, polling_config_entry)

    current_account_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "acc_curr"), polling_config_entry.entry_id
    )
    joint_account_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "acc_joint"), polling_config_entry.entry_id
    )
    pot_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "pot_joint"), polling_config_entry.entry_id
    )

    assert current_account_device is not None
    assert current_account_device.name == "Current Account"
    assert joint_account_device is not None
    assert joint_account_device.name == "Joint Account — Jake Martin & Jane Martin"
    assert pot_device is not None
    assert pot_device.name == "Holiday"


async def test_joint_account_owners_with_same_name(
    hass: HomeAssistant,
    polling_config_entry: MockConfigEntry,
    monzo: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test distinct joint owners can have the same preferred name."""
    monzo.user_account.accounts.return_value = [
        {
            **TEST_ACCOUNTS[0],
            "id": "acc_joint",
            "name": "Joint Account",
            "owners": [
                {
                    "user_id": str(USER_ID),
                    "preferred_name": "Alex Smith",
                },
                {
                    "user_id": "another-user",
                    "preferred_name": "Alex Smith",
                },
            ],
        }
    ]

    await setup_integration(hass, polling_config_entry)

    account_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "acc_joint"), polling_config_entry.entry_id
    )
    assert account_device is not None
    assert account_device.name == "Joint Account — Alex Smith & Alex Smith"


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
    await hass.async_block_till_done(wait_background_tasks=True)
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

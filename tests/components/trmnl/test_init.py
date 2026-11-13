"""Test the TRMNL initialization."""

from dataclasses import replace
from datetime import timedelta
from http import HTTPStatus
from time import time
from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.plugins import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError

from homeassistant.components.trmnl.const import CLIENT_ID, DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, instance_id
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from . import ACCOUNT_SUBJECT, setup_integration


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the TRMNL device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_connection(
        (CONNECTION_NETWORK_MAC, "B0:A6:04:AA:BB:CC"), mock_config_entry.entry_id
    )
    assert device
    assert device == snapshot


async def test_stale_device_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device is removed from the device registry when it disappears."""
    await setup_integration(hass, mock_config_entry)

    assert device_registry.async_get_device_by_connection(
        (CONNECTION_NETWORK_MAC, "B0:A6:04:AA:BB:CC"), mock_config_entry.entry_id
    )

    mock_trmnl_client.get_devices.return_value = []
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device_by_connection(
        (CONNECTION_NETWORK_MAC, "B0:A6:04:AA:BB:CC"), mock_config_entry.entry_id
    )


async def test_reauth_triggered_on_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test that a reauth flow is triggered when an auth error occurs."""
    mock_trmnl_client.get_devices.side_effect = TRMNLAuthenticationError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


@pytest.mark.freeze_time("2026-11-16 12:05:00+00:00")
async def test_migrate_api_key_entry(
    hass: HomeAssistant,
    mock_api_key_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test an entry made with an API key moves to OAuth without a new sign in."""
    await setup_integration(hass, mock_api_key_config_entry)

    install = (await instance_id.async_get(hass))[:8]
    mock_trmnl_client.migrate_to_oauth.assert_awaited_once_with(
        CLIENT_ID, f"{hass.config.location_name} ({install})"
    )
    assert mock_api_key_config_entry.state is ConfigEntryState.LOADED
    assert mock_api_key_config_entry.version == 2
    assert mock_api_key_config_entry.unique_id == ACCOUNT_SUBJECT
    assert mock_api_key_config_entry.data == {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": "migrated-access",
            "refresh_token": "migrated-refresh",
            "token_type": "Bearer",
            "expires_in": 7200,
            "scope": "openid profile read devices content delete",
            "expires_at": 1794830700 + 7200,
        },
    }


async def test_migrate_keeps_the_real_mac_address(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_api_key_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test a migrated entry keeps the MAC connection the API key saw, though OAuth masks it."""
    mock_api_key_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_api_key_config_entry.entry_id,
        identifiers={(DOMAIN, "42793")},
        connections={(CONNECTION_NETWORK_MAC, "B0:A6:04:AA:BB:CC")},
    )
    device = mock_trmnl_client.get_devices.return_value[0]
    mock_trmnl_client.get_devices.return_value = [
        replace(device, mac_address="••:••:••:••:BB:CC")
    ]

    await setup_integration(hass, mock_api_key_config_entry)

    entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "42793"), mock_api_key_config_entry.entry_id
    )
    assert entry
    assert entry.connections == {(CONNECTION_NETWORK_MAC, "b0:a6:04:aa:bb:cc")}


async def test_migrate_revoked_api_key(
    hass: HomeAssistant,
    mock_api_key_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test an API key TRMNL no longer accepts leaves the entry on version 1."""
    mock_trmnl_client.migrate_to_oauth.side_effect = TRMNLAuthenticationError

    await setup_integration(hass, mock_api_key_config_entry)

    assert mock_api_key_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert mock_api_key_config_entry.version == 1


@pytest.mark.parametrize("error", [TRMNLError, TimeoutError, ClientError])
async def test_migrate_retries_when_trmnl_is_unreachable(
    hass: HomeAssistant,
    mock_api_key_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
    error: type[Exception],
) -> None:
    """Test the migration is retried when TRMNL does not answer."""
    mock_trmnl_client.migrate_to_oauth.side_effect = error

    await setup_integration(hass, mock_api_key_config_entry)

    assert mock_api_key_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        mock_api_key_config_entry.error_reason_translation_key
        == "migration_connection_error"
    )
    assert mock_api_key_config_entry.version == 1


async def test_migrate_account_already_signed_in(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_key_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test an API key entry for an account already set up with OAuth is not migrated."""
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, mock_api_key_config_entry)

    assert mock_api_key_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert mock_api_key_config_entry.unique_id == "30561"


@pytest.mark.parametrize("expires_at", [time() - 60])
async def test_expired_token_refreshed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test an expired access token is refreshed before the API is called."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_trmnl_client.token == "new-access"
    assert mock_config_entry.data["token"]["refresh_token"] == "new-refresh"


@pytest.mark.parametrize("expires_at", [time() - 60])
async def test_revoked_refresh_token_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a refresh token the user revoked on TRMNL asks to sign in again."""
    aioclient_mock.post(
        OAUTH2_TOKEN, status=HTTPStatus.BAD_REQUEST, json={"error": "invalid_grant"}
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_masked_mac_address_not_a_connection(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_trmnl_client: AsyncMock,
) -> None:
    """Test the masked MAC address TRMNL gives a connected app is not registered."""
    device = mock_trmnl_client.get_devices.return_value[0]
    mock_trmnl_client.get_devices.return_value = [
        replace(device, mac_address="••:••:••:••:BB:CC")
    ]

    await setup_integration(hass, mock_config_entry)

    entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "42793"), mock_config_entry.entry_id
    )
    assert entry
    assert entry.connections == set()

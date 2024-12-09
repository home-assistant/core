"""Tests for init module."""

import http
import time
from unittest.mock import MagicMock

import pytest

from homeassistant.components.myuplink.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import UNIQUE_ID

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["unauthorized", "internal_server_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    "load_systems_file",
    [load_fixture("systems.json", DOMAIN)],
)
async def test_devices_created_count(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that one device is created."""
    await setup_integration(hass, mock_config_entry)

    assert len(device_registry.devices) == 1


async def test_devices_multiple_created_count(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that multiple devices are created."""
    await setup_integration(hass, mock_config_entry)

    assert len(device_registry.devices) == 2


async def test_migrate_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_myuplink_client: MagicMock,
    expires_at: float,
    access_token: str,
) -> None:
    """Test migration of config entry."""
    mock_entry_v1_1 = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="myUplink test",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": access_token,
                "scope": "WRITESYSTEM READSYSTEM offline_access",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
        entry_id="myuplink_test",
    )

    await setup_integration(hass, mock_entry_v1_1)
    assert mock_entry_v1_1.version == 1
    assert mock_entry_v1_1.minor_version == 2
    assert mock_entry_v1_1.unique_id == UNIQUE_ID

"""Tests for init module."""

import http
import time
from unittest.mock import MagicMock

from aiohttp import ClientConnectionError
from pymiele import OAUTH2_TOKEN
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = mock_config_entry

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
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


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test failure while refreshing token with a ClientError."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        exc=ClientConnectionError(),
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_devices_multiple_created_count(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that multiple devices are created."""
    await setup_integration(hass, mock_config_entry)

    assert len(device_registry.devices) == 4


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "Dummy_Appliance_1")}
    )
    assert device_entry is not None
    assert device_entry == snapshot

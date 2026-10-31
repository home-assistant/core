"""Test the Proxmox VE binary sensor platform."""

from unittest.mock import MagicMock, patch

import aiohttp
from aioproxmox.exceptions import ProxmoxAPIError, ProxmoxAuthError
from aioproxmox.model import PVEPermissions
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.coordinator import DEFAULT_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import PVEVMUSER_PERMISSIONS, setup_integration


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("exception"),
    [
        (ProxmoxAuthError("Invalid credentials")),
        (aiohttp.ClientSSLError(MagicMock(), OSError("SSL handshake failed"))),
        (TimeoutError("Connection timed out")),
        (ProxmoxAPIError(404, "status_message", "cluster/resources")),
        (aiohttp.ClientConnectionError("Connection error")),
    ],
    ids=[
        "auth_error",
        "ssl_error",
        "connect_timeout",
        "resource_exception",
        "connection_error",
    ],
)
async def test_refresh_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test entities go unavailable after coordinator refresh failures."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_proxmox_client.cluster.resources.side_effect = exception

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.ct_nginx_status")
    assert state.state == STATE_UNAVAILABLE


async def test_binary_sensors_according_to_permissions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that binary_sensors are created when allowed."""

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert "binary_sensor.pve1_status" in {e.entity_id for e in entries}
    assert "binary_sensor.pve1_backup_status" in {e.entity_id for e in entries}


async def test_binary_sensors_absent_according_to_permissions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that binary_sensors are not created when not allowed."""
    mock_proxmox_client.access.permissions.return_value = (
        PVEPermissions.from_api_response(PVEVMUSER_PERMISSIONS)
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert "binary_sensor.pve1_status" in {e.entity_id for e in entries}
    assert "binary_sensor.pve1_backup_status" not in {e.entity_id for e in entries}

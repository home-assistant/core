"""Test the Proxmox VE binary sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import pytest
import requests
from requests.exceptions import ConnectTimeout, SSLError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.proxmoxve.coordinator import DEFAULT_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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
        (
            AuthenticationError("Invalid credentials"),
            "invalid_auth",
        ),
        (
            SSLError("SSL handshake failed"),
            "ssl_error",
        ),
        (
            ConnectTimeout("Connection timed out"),
            "connect_timeout",
        ),
        (
            ResourceException,
            "resource_exception",
        ),
        (
            requests.exceptions.ConnectionError,
            "connection_error",
        ),
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

    mock_proxmox_client.nodes.get.side_effect = exception

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("binary_sensor.ct_nginx_status")
    assert state.state == STATE_UNAVAILABLE

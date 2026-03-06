"""Tests for the Proxmox VE update platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "update.funny_chatelet_image_update_available"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_update_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Proxmox VE update entities."""
    with patch(
        "homeassistant.components.proxmoxve._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass,
            entity_registry,
            snapshot,
            mock_config_entry.entry_id,
        )


async def test_update_install(
    hass: HomeAssistant,
    mock_proxmox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful Proxmox VE node update installation."""
    with patch(
        "homeassistant.components.proxmoxve._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    mock_proxmox_client.container_recreate.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (PortainerAuthenticationError("auth"), "invalid_auth_no_details"),
        (PortainerConnectionError("conn"), "cannot_connect_no_details"),
    ],
)
async def test_update_install_errors(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test container image update install error handling."""
    mock_portainer_client.container_recreate.side_effect = exception

    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )


async def test_update_using_cache(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the update entity uses the cache and doesn't call the API."""
    mock_portainer_watcher.last_check = 1234

    with (
        patch(
            "homeassistant.components.portainer.coordinator.time.monotonic",
            return_value=1235.0,
        ),
        patch(
            "homeassistant.components.portainer._PLATFORMS",
            [Platform.UPDATE],
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    # Reset call counts, since it needs to be measured what happens in this sequence
    mock_portainer_client.inspect_container.reset_mock()
    mock_portainer_client.get_image.reset_mock()

    # Trigger a refresh, but it should use the cache
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    mock_portainer_client.inspect_container.assert_not_called()
    mock_portainer_client.get_image.assert_not_called()

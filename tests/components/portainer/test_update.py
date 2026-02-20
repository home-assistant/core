"""Tests for the Portainer update platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import PortainerImageUpdateStatus
from pyportainer.watcher import PortainerImageWatcherResult
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "update.funny_chatelet"
FUNNY_CHATELET_ID = "aa86eacfb3b3ed4cd362c1e88fc89a53908ad05fb3a4103bca3f9b28292d14bf"
ENDPOINT_ID = 1


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("mock_portainer_client")
async def test_update_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Portainer update entities."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
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
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful container image update installation."""
    mock_portainer_watcher.results = {
        (ENDPOINT_ID, FUNNY_CHATELET_ID): PortainerImageWatcherResult(
            endpoint_id=ENDPOINT_ID,
            container_id=FUNNY_CHATELET_ID,
            status=PortainerImageUpdateStatus(
                update_available=True,
                local_digest="sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96",
                registry_digest="sha256:newdigest123456789",
            ),
        )
    }

    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    mock_portainer_client.container_recreate.assert_called_once()


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
    mock_portainer_watcher.results = {
        (ENDPOINT_ID, FUNNY_CHATELET_ID): PortainerImageWatcherResult(
            endpoint_id=ENDPOINT_ID,
            container_id=FUNNY_CHATELET_ID,
            status=PortainerImageUpdateStatus(
                update_available=True,
                local_digest="sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96",
                registry_digest="sha256:newdigest123456789",
            ),
        )
    }
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

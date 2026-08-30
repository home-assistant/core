"""Tests for the Portainer update platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import ATTR_INSTALLED_VERSION
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


@pytest.mark.parametrize("repo_digests", [None, []], ids=["missing", "empty"])
async def test_update_installed_version_without_repo_digest(
    hass: HomeAssistant,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    repo_digests: list[str] | None,
) -> None:
    """Test an image that was never pulled from a registry has no installed version."""
    mock_portainer_client.get_image.return_value.repo_digests = repo_digests

    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INSTALLED_VERSION] is None


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
    mock_portainer_client.get_image.reset_mock()

    # Trigger a refresh, but it should use the cache
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    mock_portainer_client.get_image.assert_not_called()

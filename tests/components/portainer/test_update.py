"""Tests for the Portainer update platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.portainer.update import (
    _format_version,
    _release_url,
    _short_digest,
)
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


@pytest.mark.parametrize(
    ("digest", "expected"),
    [
        pytest.param(None, None, id="none"),
        pytest.param(
            "sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb",
            "sha256:afcc7f1ac1b4",
            id="full_digest",
        ),
        pytest.param(
            "example@sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb",
            "sha256:afcc7f1ac1b4",
            id="repo_prefix",
        ),
    ],
)
def test_short_digest(digest: str | None, expected: str | None) -> None:
    """Test _short_digest produces a 12-character Docker-style short form."""
    assert _short_digest(digest) == expected


@pytest.mark.parametrize(
    ("digest", "repo_tags", "expected"),
    [
        pytest.param(None, None, None, id="no_digest"),
        pytest.param(
            "sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb",
            None,
            "sha256:afcc7f1ac1b4",
            id="no_repo_tags",
        ),
        pytest.param(
            "sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb",
            ["app:latest", "app:1.0"],
            "app:latest (sha256:afcc7f1ac1b4)",
            id="with_repo_tags",
        ),
    ],
)
def test_format_version(
    digest: str | None, repo_tags: list[str] | None, expected: str | None
) -> None:
    """Test _format_version combines tag and short digest."""
    assert _format_version(digest, repo_tags) == expected


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        pytest.param(None, None, id="none"),
        pytest.param(
            "ubuntu:latest",
            "https://hub.docker.com/r/ubuntu/tags?name=latest",
            id="docker_hub_bare_name",
        ),
        pytest.param(
            "ubuntu",
            "https://hub.docker.com/r/ubuntu/tags?name=latest",
            id="docker_hub_bare_no_tag",
        ),
        pytest.param(
            "docker.io/library/ubuntu:latest",
            "https://hub.docker.com/_/ubuntu/tags?name=latest",
            id="docker_io_library",
        ),
        pytest.param(
            "docker.io/lissy93/dashy:latest",
            "https://hub.docker.com/r/lissy93/dashy/tags?name=latest",
            id="docker_io_user",
        ),
        pytest.param(
            "ghcr.io/owner/myapp:v1.0",
            "https://github.com/owner/myapp/pkgs/container/myapp",
            id="ghcr_io",
        ),
        pytest.param(
            "ghcr.io/org/sub/app:latest",
            None,
            id="ghcr_io_nested",
        ),
        pytest.param(
            "quay.io/prometheus/prometheus:latest",
            None,
            id="unknown_registry",
        ),
    ],
)
def test_release_url(image: str | None, expected: str | None) -> None:
    """Test _release_url returns tag page links for known registries only."""
    assert _release_url(image) == expected

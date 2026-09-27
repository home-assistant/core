"""Tests for the Portainer update platform."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import DockerContainer, PortainerImageUpdateStatus
from pyportainer.watcher import PortainerImageWatcherResult
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.components.portainer.coordinator import DEFAULT_SCAN_INTERVAL
from homeassistant.components.update import ATTR_INSTALLED_VERSION, ATTR_LATEST_VERSION
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)

ENTITY_ID = "update.funny_chatelet_image_update_available"
CONTAINER_IMAGE = "docker.io/library/ubuntu:latest"
INSTALLED_DIGEST = (
    "sha256:afcc7f1ac1b49db317a7196c902e61c6c3c4607d63599ee1a82d702d249a0ccb"
)
RECREATED_CONTAINER_ID = (
    "0011facfb3b3ed4cd362c1e88fc89a53908ad05fb3a4103bca3f9b28292d14bf"
)


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


async def _watch_all_containers(hass: HomeAssistant, watcher: MagicMock) -> None:
    """Give the watcher a result for every container, as after its first run."""
    containers = cast(
        list[dict[str, Any]],
        await async_load_json_array_fixture(hass, "containers.json", DOMAIN),
    )
    watcher.results = {
        (1, container["Id"]): PortainerImageWatcherResult(
            endpoint_id=1,
            container_id=container["Id"],
            status=PortainerImageUpdateStatus(
                update_available=True,
                local_digest=INSTALLED_DIGEST,
                registry_digest="sha256:newdigest123456789",
            ),
        )
        for container in containers
    }
    watcher.last_check = 1234


async def _recreate_container(hass: HomeAssistant, client: AsyncMock) -> None:
    """Give the funny_chatelet container a new ID, as a recreate does."""
    containers = cast(
        list[dict[str, Any]],
        await async_load_json_array_fixture(hass, "containers.json", DOMAIN),
    )
    recreated = next(
        container for container in containers if "/funny_chatelet" in container["Names"]
    )
    recreated["Id"] = RECREATED_CONTAINER_ID
    client.get_containers.return_value = [
        DockerContainer.from_dict(container) for container in containers
    ]


async def test_update_recreated_container(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a recreated container gets its image checked instead of staying unknown."""
    await _watch_all_containers(hass, mock_portainer_watcher)

    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # The watcher only has a result for the old container ID
    await _recreate_container(hass, mock_portainer_client)
    mock_portainer_client.container_image_status.return_value = (
        PortainerImageUpdateStatus(
            update_available=False,
            local_digest=INSTALLED_DIGEST,
            registry_digest=INSTALLED_DIGEST,
        )
    )

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_portainer_client.container_image_status.assert_called_once_with(
        1, CONTAINER_IMAGE
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_LATEST_VERSION] == "sha256:afcc7f1ac1b4"

    # The result is kept until the watcher runs again, not fetched every poll
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_portainer_client.container_image_status.assert_called_once()


async def test_update_recreated_container_before_watcher_ran(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a container is left to the watcher's first run."""
    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    await _recreate_container(hass, mock_portainer_client)

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_portainer_client.container_image_status.assert_not_called()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(PortainerConnectionError("conn"), id="connection"),
        pytest.param(PortainerAuthenticationError("auth"), id="authentication"),
    ],
)
async def test_update_recreated_container_check_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_portainer_client: AsyncMock,
    mock_portainer_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test a failed image check leaves the update unknown without failing the refresh."""
    await _watch_all_containers(hass, mock_portainer_watcher)

    with patch(
        "homeassistant.components.portainer._PLATFORMS",
        [Platform.UPDATE],
    ):
        await setup_integration(hass, mock_config_entry)

    await _recreate_container(hass, mock_portainer_client)
    mock_portainer_client.container_image_status.side_effect = exception

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.last_update_success
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

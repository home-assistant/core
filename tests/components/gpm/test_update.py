"""Tests for the GPM update entity."""

import pytest

from homeassistant.components.gpm._manager import (
    IntegrationRepositoryManager,
    RepositoryManager,
    ResourceRepositoryManager,
)
from homeassistant.components.gpm.const import GIT_SHORT_HASH_LEN
from homeassistant.components.gpm.update import GPMUpdateEntity, UpdateStrategy
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry."""
    state = hass.states.get("update.awesome_component")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "off"


async def test_integration_properties(
    integration_manager: IntegrationRepositoryManager,
) -> None:
    """Test properties of integration fetched during async_update."""
    await integration_manager.clone()
    await integration_manager.checkout("v0.9.9")
    await integration_manager.install()
    entity = GPMUpdateEntity(integration_manager)
    await entity.async_update()
    assert entity.installed_version == "v0.9.9"
    assert entity.latest_version == "v1.0.0"
    assert entity.name == "awesome_component"
    assert entity.unique_id == "github_com.user.awesome_component"
    assert (
        entity.entity_picture
        == "https://brands.home-assistant.io/_/awesome_component/icon.png"
    )
    assert integration_manager.fetch.await_count == 1


async def test_resource_properties(resource_manager: ResourceRepositoryManager) -> None:
    """Test properties of resource fetched during async_update."""
    await resource_manager.clone()
    await resource_manager.checkout("v0.9.9")
    await resource_manager.install()
    entity = GPMUpdateEntity(resource_manager)
    await entity.async_update()
    assert entity.installed_version == "v0.9.9"
    assert entity.latest_version == "v1.0.0"
    assert entity.name == "awesome_card"
    assert entity.unique_id == "github_com.user.awesome_card"
    assert entity.entity_picture is None
    assert resource_manager.fetch.await_count == 1


async def test_versions_substr(manager: RepositoryManager) -> None:
    """Test that GIT commit SHAs are shortened in UI."""
    manager.update_strategy = UpdateStrategy.LATEST_COMMIT
    await manager.install()
    entity = GPMUpdateEntity(manager)
    await entity.async_update()
    assert len(entity.installed_version) == GIT_SHORT_HASH_LEN
    assert len(entity.latest_version) == GIT_SHORT_HASH_LEN


@pytest.mark.parametrize("version", ["v0.8.8", "v1.0.0", "v2.0.0beta2", None])
async def test_install(
    manager: RepositoryManager, version: str | None, request: pytest.FixtureRequest
) -> None:
    """Test update installation."""
    await manager.clone()
    await manager.checkout("v0.9.9")
    await manager.install()
    manager.checkout.reset_mock()
    entity = GPMUpdateEntity(manager)
    await entity.async_update()
    await entity.async_install(version=version, backup=False)
    assert manager.checkout.await_count == 1


async def test_install_same_version(manager: RepositoryManager) -> None:
    """Test update installation fails due to the same version."""
    await manager.clone()
    await manager.checkout("v0.9.9")
    await manager.install()
    manager.checkout.reset_mock()
    entity = GPMUpdateEntity(manager)
    await entity.async_update()
    with pytest.raises(HomeAssistantError):
        await entity.async_install(version="v0.9.9", backup=False)
    assert manager.checkout.await_count == 0


async def test_install_non_existing_version(manager: RepositoryManager) -> None:
    """Test update installation fails due to non-existing version."""
    await manager.clone()
    await manager.checkout("v0.9.9")
    await manager.install()
    manager.checkout.reset_mock()
    entity = GPMUpdateEntity(manager)
    await entity.async_update()
    with pytest.raises(HomeAssistantError):
        await entity.async_install(version="non-existing", backup=False)
    assert manager.checkout.await_count == 1

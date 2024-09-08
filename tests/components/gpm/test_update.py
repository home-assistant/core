"""Tests for the GPM update entity."""

import pytest

from homeassistant.components.gpm.update import GPMUpdateEntity, UpdateStrategy
from homeassistant.exceptions import HomeAssistantError


async def test_integration_properties(mock_integration_manager) -> None:
    """Test properties of integration fetched during async_update."""
    entity = GPMUpdateEntity(mock_integration_manager)
    await entity.async_update()
    assert entity.installed_version == "v0.9.9"
    assert entity.latest_version == "v1.0.0"
    assert entity.name == "awesome_component"
    assert entity.unique_id == "github_com.user.awesome_component"
    assert (
        entity.entity_picture
        == "https://brands.home-assistant.io/_/awesome_component/icon.png"
    )
    assert mock_integration_manager.fetch.await_count == 1


async def test_resource_properties(mock_resource_manager) -> None:
    """Test properties of resource fetched during async_update."""
    entity = GPMUpdateEntity(mock_resource_manager)
    await entity.async_update()
    assert entity.installed_version == "v0.9.9"
    assert entity.latest_version == "v1.0.0"
    assert entity.name == "awesome_card"
    assert entity.unique_id == "github_com.user.awesome_card"
    assert entity.entity_picture is None
    assert mock_resource_manager.fetch.await_count == 1


async def test_versions_substr(mock_resource_manager) -> None:
    """Test that GIT commit SHAs are shortened in UI."""
    mock_resource_manager.update_strategy = UpdateStrategy.LATEST_COMMIT
    mock_resource_manager.get_current_version.return_value = (
        "d98061dd815fbf3ead679d9f744328f5217da68a"
    )
    mock_resource_manager.get_latest_version.return_value = (
        "690a323d9a879eff007cc6f7f742293fd9464b20"
    )
    entity = GPMUpdateEntity(mock_resource_manager)
    await entity.async_update()
    assert entity.installed_version == "d98061d"
    assert entity.latest_version == "690a323"


@pytest.mark.parametrize("version", ["0.8.8", "1.0.0", "2.0.0beta5", None])
async def test_install(mock_integration_manager, version) -> None:
    """Test update installation."""
    entity = GPMUpdateEntity(mock_integration_manager)
    await entity.async_update()
    await entity.async_install(version=version, backup=False)
    assert mock_integration_manager.checkout.await_count == 1


async def test_install_same_version(mock_integration_manager) -> None:
    """Test failed update installation."""
    entity = GPMUpdateEntity(mock_integration_manager)
    await entity.async_update()
    with pytest.raises(HomeAssistantError):
        await entity.async_install(version="v0.9.9", backup=False)
    assert mock_integration_manager.checkout.await_count == 0

"""Test repositories that GitHub gave a new id, after they were created again."""

from pathlib import Path
from typing import Any

import pytest

from homeassistant.components.marketplace.base import Repositories
from homeassistant.components.marketplace.const import DOMAIN, STORAGE_VERSION
from homeassistant.components.marketplace.enums import MarketplaceStage
from homeassistant.components.marketplace.repositories.base import Repository
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    create_install_folders,
    get_marketplace,
    mocked_response,
    setup_integration,
)
from .conftest import MarketplaceResponses
from .const import REPOSITORY_INTEGRATION, REPOSITORY_INTEGRATION_ID

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_object_fixture,
)

INTEGRATION_FEED = "https://data-v2.hacs.xyz/integration/data.json"
NEW_ID = "2296269"


def _feed_entry() -> dict[str, Any]:
    """Return how the catalog lists the basic integration."""
    feed = load_json_object_fixture(
        "proxy/data-v2.hacs.xyz/integration/data.json", DOMAIN
    )
    return feed[REPOSITORY_INTEGRATION_ID]


def _serve_feed(response_mocker: MarketplaceResponses, feed: dict[str, Any]) -> None:
    """Serve the given integration catalog."""
    response_mocker.add(
        INTEGRATION_FEED,
        mocked_response(INTEGRATION_FEED, json_content=feed),
        keep=True,
    )


@pytest.mark.usefixtures("stored_repositories")
async def test_installed_repository_takes_the_new_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    response_mocker: MarketplaceResponses,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test an installed repository created again on GitHub keeps what it had."""
    _serve_feed(response_mocker, {NEW_ID: _feed_entry()})

    await setup_integration(hass, mock_config_entry)
    marketplace = get_marketplace(hass)

    assert marketplace.stage is MarketplaceStage.RUNNING
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    assert repository.data.id == NEW_ID
    assert repository.data.installed
    assert marketplace.repositories.is_default(NEW_ID)
    assert marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID) is None

    # Its entities and device follow it to the new id
    assert entity_registry.async_get_entity_id(Platform.UPDATE, DOMAIN, NEW_ID)
    assert not entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, REPOSITORY_INTEGRATION_ID
    )
    entry_id = mock_config_entry.entry_id
    assert device_registry.async_get_device_by_identifier((DOMAIN, NEW_ID), entry_id)
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, REPOSITORY_INTEGRATION_ID), entry_id
    )


@pytest.mark.usefixtures("stored_repositories")
async def test_catalog_lists_a_repository_twice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test a name listed under two ids does not stop the Marketplace starting."""
    _serve_feed(
        response_mocker,
        {REPOSITORY_INTEGRATION_ID: _feed_entry(), NEW_ID: _feed_entry()},
    )

    await setup_integration(hass, mock_config_entry)
    marketplace = get_marketplace(hass)

    assert marketplace.stage is MarketplaceStage.RUNNING
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    assert repository.data.id == NEW_ID
    assert repository.data.installed


async def test_stored_under_two_ids(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the installed entry wins when stored data holds a name twice."""
    stored = await async_load_json_object_fixture(
        hass, "stored_repositories.json", DOMAIN
    )
    leftover = {
        key: value
        for key, value in stored[REPOSITORY_INTEGRATION_ID].items()
        if key not in ("installed", "version_installed", "installed_commit")
    }
    hass_storage[f"{DOMAIN}.repositories"] = {
        "version": STORAGE_VERSION,
        # The leftover comes last, so the order does not pick the right one
        "data": {**stored, NEW_ID: leftover},
    }
    create_install_folders(Path(hass.config.config_dir), stored)

    await setup_integration(hass, mock_config_entry)
    marketplace = get_marketplace(hass)

    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    assert repository.data.installed
    assert repository.data.id == REPOSITORY_INTEGRATION_ID


@pytest.mark.usefixtures("init_integration")
async def test_unregister_leaves_the_live_repository(
    mock_repository: Repository, mock_repository_integration: Repository
) -> None:
    """Test unregistering a stale copy keeps the one that took the name."""
    repositories = Repositories()
    mock_repository.data.full_name = "test/test"
    mock_repository.data.id = "1"
    mock_repository_integration.data.id = "2"
    repositories.register(mock_repository)
    repositories.register(mock_repository_integration)

    repositories.unregister(mock_repository)

    assert repositories.get_by_full_name("test/test") is mock_repository_integration
    assert repositories.get_by_id("2") is mock_repository_integration


@pytest.mark.usefixtures("init_integration")
async def test_renamed_repository_keeps_what_it_had(
    mock_repository: Repository, mock_repository_integration: Repository
) -> None:
    """Test a repository renamed on GitHub is found by its new name only."""
    repositories = Repositories()
    mock_repository.data.full_name = "owner/old-name"
    mock_repository.data.id = "42"
    repositories.register(mock_repository, default=True)

    # The catalog lists the same id under the new name
    mock_repository_integration.data.full_name = "owner/New-Name"
    mock_repository_integration.data.id = "42"
    repositories.register(mock_repository_integration)

    assert repositories.get_by_full_name("owner/new-name") is mock_repository
    assert repositories.get_by_full_name("owner/old-name") is None
    assert repositories.is_default("42")

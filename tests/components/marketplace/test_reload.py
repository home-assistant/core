"""Tests that what the Marketplace knows survives a reload or a restart."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.components.marketplace.enums import RepositoryCategory
from homeassistant.components.marketplace.update import RepositoryUpdateEntity
from homeassistant.components.marketplace.utils.validate import (
    VALIDATE_FETCHED_V2_REPO_DATA,
)
from homeassistant.const import EVENT_HOMEASSISTANT_START, Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import get_marketplace
from .const import REPOSITORY_INTEGRATION_ID, REPOSITORY_PLUGIN_ID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator

CUSTOM_REPOSITORY = "hacs-test-org/integration-basic-custom"


async def _async_reload(hass: HomeAssistant, marketplace: MarketplaceManager) -> None:
    """Reload the config entry of the Marketplace."""
    assert marketplace.configuration.config_entry is not None
    assert await hass.config_entries.async_reload(
        marketplace.configuration.config_entry.entry_id
    )
    await hass.async_block_till_done()


async def test_added_custom_repository_survives_a_reload(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test a custom repository added by hand is kept, even when not downloaded."""
    await marketplace.async_register_repository(
        CUSTOM_REPOSITORY, RepositoryCategory.INTEGRATION
    )
    assert marketplace.repositories.get_by_full_name(CUSTOM_REPOSITORY)
    await marketplace.data.async_write()

    await _async_reload(hass, marketplace)

    assert get_marketplace(hass).repositories.get_by_full_name(CUSTOM_REPOSITORY)


async def test_forgotten_custom_repository_is_gone_after_a_reload(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a custom repository removed from the list stays removed."""
    await marketplace.async_register_repository(
        CUSTOM_REPOSITORY, RepositoryCategory.INTEGRATION
    )
    repository = marketplace.repositories.get_by_full_name(CUSTOM_REPOSITORY)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repositories/remove", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    await _async_reload(hass, marketplace)

    assert (
        get_marketplace(hass).repositories.get_by_full_name(CUSTOM_REPOSITORY) is None
    )


@pytest.mark.parametrize("github_token", [None])
async def test_config_flow_flag_survives_a_reload(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test a downloaded integration keeps knowing it is set up from the UI."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    await repository.async_download_repository()
    assert repository.data.config_flow

    await _async_reload(hass, marketplace)

    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert repository.data.installed
    assert repository.data.config_flow


async def test_pending_restart_survives_a_reload(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test a reload does not pretend the downloaded code is loaded."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    await repository.async_download_repository()
    assert repository.pending_restart

    await _async_reload(hass, marketplace)

    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert repository.pending_restart


async def test_new_download_gets_its_pre_release_switch(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a first download creates all of its entities right away."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/download", "repository": REPOSITORY_PLUGIN_ID}
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, REPOSITORY_PLUGIN_ID
    )
    assert entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, REPOSITORY_PLUGIN_ID
    )


async def test_beta_release_notes_keep_the_stable_version(
    marketplace: MarketplaceManager,
) -> None:
    """Test reading release notes with pre-releases on does not make one stable."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = True
    repository.data.installed_version = "1.0.0"
    repository.data.last_version = "2.0.0"
    repository.data.prerelease = "3.0.0"
    repository.data.show_beta = True
    repository.data.published_tags = []
    entity = RepositoryUpdateEntity(marketplace, repository)

    assert await entity.async_release_notes()
    repository.data.show_beta = False

    # The recorded releases hold 2.0.0 as a draft, 1.0.0 is the newest stable one
    assert repository.display_available_version == "1.0.0"


async def test_integer_catalog_timestamp_can_be_stored(
    marketplace: MarketplaceManager,
) -> None:
    """Test a timestamp the catalog sends as a whole number is stored like any."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    data = await marketplace.data_client.get_data(
        RepositoryCategory.INTEGRATION, validate=True
    )
    data[repository.data.id]["last_fetched"] = 2000000000
    VALIDATE_FETCHED_V2_REPO_DATA[RepositoryCategory.INTEGRATION](
        data[repository.data.id]
    )

    with patch.object(
        marketplace.data_client, "get_data", AsyncMock(return_value=data)
    ):
        await marketplace.async_get_category_repositories_from_catalog(
            RepositoryCategory.INTEGRATION
        )
    await marketplace.data.async_write()

    assert repository.data.last_fetched == dt_util.utc_from_timestamp(2000000000)


async def test_catalog_removal_is_noticed_while_running(
    hass: HomeAssistant, marketplace: MarketplaceManager, freezer: FrozenDateTimeFactory
) -> None:
    """Test a repository the catalog removes is noticed without a restart."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    await repository.async_download_repository()
    get_data = marketplace.data_client.get_data

    async def catalog(section: str | None, *, validate: bool) -> object:
        if section == "removed":
            return [
                {
                    "repository": repository.data.full_name,
                    "removal_type": "removed",
                    "reason": "Unmaintained",
                }
            ]
        return await get_data(section, validate=validate)

    with patch.object(marketplace.data_client, "get_data", catalog):
        freezer.tick(timedelta(hours=6, seconds=1))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    assert marketplace.repositories.is_removed(repository.data.full_name)


async def test_unloaded_before_start_runs_no_startup_tasks(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an entry unloaded before Home Assistant started leaves its tasks."""
    hass.set_state(CoreState.not_running)
    mock_config_entry.add_to_hass(hass)

    with patch.object(MarketplaceManager, "startup_tasks") as startup_tasks:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

    startup_tasks.assert_not_called()

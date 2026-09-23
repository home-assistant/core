"""Tests for the Marketplace setup."""

from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from aiogithubapi import GitHubAuthenticationException, GitHubException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.marketplace import async_remove_config_entry_device
from homeassistant.components.marketplace.const import DOMAIN, LEGACY_HACS_SYSTEM_ID
from homeassistant.components.marketplace.enums import DisabledReason
from homeassistant.components.marketplace.exceptions import MarketplaceError
from homeassistant.components.marketplace.utils.data import MarketplaceData
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import assert_api_usage, get_marketplace, setup_integration
from .const import (
    REPOSITORY_INTEGRATION,
    REPOSITORY_INTEGRATION_ID,
    REPOSITORY_PLUGIN,
    REPOSITORY_PLUGIN_ID,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry loads and unloads again."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not get_marketplace(hass).system.disabled

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        pytest.param(
            GitHubAuthenticationException("Bad credentials"),
            ConfigEntryState.SETUP_ERROR,
            id="authentication",
        ),
        pytest.param(
            GitHubException("GitHub is having a moment"),
            ConfigEntryState.SETUP_RETRY,
            id="github_api",
        ),
        pytest.param(
            MarketplaceError("Something went wrong"),
            ConfigEntryState.SETUP_RETRY,
            id="marketplace",
        ),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test a failure while setting up leaves the entry for core to handle."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(MarketplaceData, "restore", side_effect=side_effect):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is state


async def test_setup_retries_without_restored_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test data that can not be restored is retried instead of disabling."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(MarketplaceData, "restore", return_value=False):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("reason", "state"),
    [
        pytest.param(
            DisabledReason.INVALID_TOKEN,
            ConfigEntryState.SETUP_ERROR,
            id="invalid_token",
        ),
        pytest.param(
            DisabledReason.RATE_LIMIT,
            ConfigEntryState.SETUP_RETRY,
            id="rate_limit",
        ),
    ],
)
async def test_setup_with_a_disabled_marketplace(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    reason: DisabledReason,
    state: ConfigEntryState,
) -> None:
    """Test a Marketplace that ends up disabled while setting up fails the setup."""

    async def _disable(self: MarketplaceData) -> bool:
        """Restore the data, but leave the Marketplace disabled."""
        self.marketplace.disable(reason)
        return True

    mock_config_entry.add_to_hass(hass)

    with patch.object(MarketplaceData, "restore", _disable):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is state


async def test_setup_asks_to_reauthenticate_for_an_invalid_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an invalid token during setup asks the user to reauthenticate."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        MarketplaceData,
        "restore",
        side_effect=GitHubAuthenticationException("Bad credentials"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("stored_repositories")
async def test_entities_for_downloaded_repositories(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test each downloaded repository gets an update and a switch entity."""
    await setup_integration(hass, mock_config_entry)

    marketplace = get_marketplace(hass)
    assert {
        repo.data.full_name for repo in marketplace.repositories.list_downloaded
    } == {
        REPOSITORY_INTEGRATION,
        REPOSITORY_PLUGIN,
    }

    # The platforms are set up concurrently, so the registry order is not fixed
    entities = sorted(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id),
        key=lambda entity: entity.entity_id,
    )
    assert [entity.entity_id for entity in entities] == [
        "switch.basic_integration_pre_release",
        "switch.basic_plugin_pre_release",
        "update.basic_integration_update",
        "update.basic_plugin_update",
    ]
    assert entities == snapshot(name="entities")

    assert hass.states.get("update.basic_integration_update") == snapshot(
        name="update_state"
    )


@pytest.mark.usefixtures("stored_repositories")
async def test_setup_request_volume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting up does not make a request per known repository."""
    await setup_integration(hass, mock_config_entry)

    assert_api_usage(aioclient_mock, snapshot)


@pytest.mark.usefixtures("stored_repositories")
async def test_stored_repository_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the stored repository ids survive a restore."""
    await setup_integration(hass, mock_config_entry)

    marketplace = get_marketplace(hass)
    assert marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)


@pytest.mark.parametrize(
    ("identifiers", "message"),
    [
        pytest.param(
            {("other_domain", "123456"), ("another_domain", "789")},
            "it does not belong to a repository in the Marketplace",
            id="other_domains_only",
        ),
        pytest.param(
            set(),
            "it does not belong to a repository in the Marketplace",
            id="no_identifiers",
        ),
        pytest.param(
            {(DOMAIN,), (DOMAIN, "123", "extra"), "not_a_tuple"},
            "it does not belong to a repository in the Marketplace",
            id="malformed_identifiers",
        ),
        pytest.param(
            {(DOMAIN, LEGACY_HACS_SYSTEM_ID)},
            "Cannot remove the service of the Marketplace itself",
            id="system_device",
        ),
        pytest.param(
            {("other_domain", "789"), (DOMAIN, LEGACY_HACS_SYSTEM_ID)},
            "Cannot remove the service of the Marketplace itself",
            id="system_device_among_others",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_remove_device_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    identifiers: set[Any],
    message: str,
) -> None:
    """Test removing a device that does not map to a repository is refused."""
    device_entry = MagicMock(spec=dr.DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = identifiers

    with pytest.raises(HomeAssistantError, match=message):
        await async_remove_config_entry_device(hass, mock_config_entry, device_entry)


@pytest.mark.parametrize(
    "identifiers",
    [
        pytest.param({(DOMAIN, "123456")}, id="single_identifier"),
        pytest.param(
            {("other_domain", "789"), (DOMAIN, "123456")},
            id="identifier_among_others",
        ),
        pytest.param({(DOMAIN, 123456)}, id="integer_identifier"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_remove_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    identifiers: set[Any],
) -> None:
    """Test removing a device for a repository that is not downloaded."""
    device_entry = MagicMock(spec=dr.DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = identifiers

    assert await async_remove_config_entry_device(hass, mock_config_entry, device_entry)


@pytest.mark.usefixtures("stored_repositories", "init_integration")
async def test_remove_device_still_downloaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a device for a downloaded repository is refused."""
    device_entry = MagicMock(spec=dr.DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = {(DOMAIN, REPOSITORY_INTEGRATION_ID)}

    with pytest.raises(
        HomeAssistantError,
        match=(
            f"Cannot remove the service for {REPOSITORY_INTEGRATION}, "
            "it is still downloaded"
        ),
    ):
        await async_remove_config_entry_device(hass, mock_config_entry, device_entry)


@pytest.mark.parametrize(
    ("path", "location"),
    [
        pytest.param("/hacs", "/marketplace", id="panel"),
        pytest.param(
            "/hacs/repository/1296269",
            "/marketplace/repository/1296269",
            id="repository",
        ),
        pytest.param(
            "/hacs/_my_redirect/hacs_repository",
            "/marketplace/_my_redirect/hacs_repository",
            id="my_redirect",
        ),
        pytest.param(
            "/hacs/_my_redirect/hacs_repository?owner=test&repository=test",
            "/marketplace/_my_redirect/hacs_repository?owner=test&repository=test",
            id="query_string",
        ),
    ],
)
async def test_old_panel_paths_redirect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    path: str,
    location: str,
) -> None:
    """Test that the paths of the old HACS panel redirect to the Marketplace."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(path, allow_redirects=False)

    assert response.status == HTTPStatus.MOVED_PERMANENTLY
    assert response.headers["Location"] == location


async def test_old_panel_paths_redirect_without_a_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test that a bookmark opened before login is redirected."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client_no_auth()
    response = await client.get("/hacs/repository/1296269", allow_redirects=False)

    assert response.status == HTTPStatus.MOVED_PERMANENTLY
    assert response.headers["Location"] == "/marketplace/repository/1296269"


async def test_www_directory_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a missing www directory is created for the next start."""
    assert not (config_dir / "www").exists()

    await setup_integration(hass, mock_config_entry)

    assert (config_dir / "www").is_dir()
    assert get_marketplace(hass).status.created_www_directory is True
    assert "dashboard resources are served after a restart" in caplog.text


async def test_www_directory_left_alone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that an existing www directory is not reported as created."""
    await hass.async_add_executor_job((config_dir / "www").mkdir)

    await setup_integration(hass, mock_config_entry)

    assert get_marketplace(hass).status.created_www_directory is False
    assert "dashboard resources are served after a restart" not in caplog.text

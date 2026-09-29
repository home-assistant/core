"""Tests for the Marketplace setup."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiogithubapi import (
    GitHubAuthenticationException,
    GitHubException,
    GitHubRatelimitException,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.components.marketplace import async_remove_config_entry_device
from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import DOMAIN, LEGACY_HACS_SYSTEM_ID
from homeassistant.components.marketplace.enums import DisabledReason
from homeassistant.components.marketplace.exceptions import (
    GitHubRateLimitError,
    MarketplaceError,
)
from homeassistant.components.marketplace.utils.data import MarketplaceData
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_SYSTEM,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import assert_api_usage, get_marketplace, github_api_calls, setup_integration
from .const import (
    REPOSITORY_INTEGRATION,
    REPOSITORY_INTEGRATION_ID,
    REPOSITORY_PLUGIN,
    REPOSITORY_PLUGIN_ID,
)

from tests.common import MockConfigEntry, async_fire_time_changed
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


async def test_panel_registered_when_setup_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the panel is there to explain a setup that failed."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(MarketplaceData, "restore", return_value=False):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    panel = hass.data[DATA_PANELS][DOMAIN]
    assert panel.component_name == DOMAIN
    assert panel.require_admin is True
    assert panel.show_in_sidebar is False


async def test_restart_issues_removed_on_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the restart issues of earlier installs go once Home Assistant started."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "restart_required_1296269_tags/1.0.0",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="restart_required",
        translation_placeholders={"name": "Basic integration"},
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "removed_1296269",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="removed",
        translation_placeholders={
            "name": "Basic integration",
            "reason": "it is gone",
            "repository_id": "1296269",
        },
    )

    await setup_integration(hass, mock_config_entry)

    assert not issue_registry.async_get_issue(
        DOMAIN, "restart_required_1296269_tags/1.0.0"
    )
    # Anything else the Marketplace reported stays
    assert issue_registry.async_get_issue(DOMAIN, "removed_1296269")


async def test_legacy_plugin_path(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
) -> None:
    """Test installed plugins still load from the path HACS served them on."""
    plugin = config_dir / "www" / "community" / "plugin-basic" / "plugin-basic.js"
    plugin.parent.mkdir(parents=True)
    plugin.write_text("customElements.define()", encoding="utf-8")

    await setup_integration(hass, mock_config_entry)
    # A reload must not try to register the path a second time
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)

    client = await hass_client()
    response = await client.get("/hacsfiles/plugin-basic/plugin-basic.js")
    assert response.status == HTTPStatus.OK
    assert await response.text() == "customElements.define()"


async def test_legacy_plugin_path_without_plugins(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the old path is only served for an install that has plugins."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get("/hacsfiles/plugin-basic/plugin-basic.js")
    assert response.status == HTTPStatus.NOT_FOUND


async def test_unload_keeps_running_when_platforms_stay(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed unload leaves the Marketplace working."""
    await setup_integration(hass, mock_config_entry)
    marketplace = get_marketplace(hass)

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert not marketplace.system.disabled

    # The catalog is still refreshed on its interval
    with patch.object(
        marketplace.data_client, "get_data", AsyncMock(return_value={})
    ) as get_data:
        freezer.tick(timedelta(hours=6, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    get_data.assert_called()


async def test_unload_with_pending_queue_tasks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test queued work does not keep the entry from unloading."""
    await setup_integration(hass, mock_config_entry)
    queued = AsyncMock()
    get_marketplace(hass).queue.add(queued())

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    queued.assert_not_awaited()


async def test_unload_waits_for_a_running_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading lets an install finish, a new setup would restore under it."""
    await setup_integration(hass, mock_config_entry)
    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    release = asyncio.Event()
    finished: list[str] = []

    async def install(ref: str | None) -> None:
        await release.wait()
        finished.append("install")

    with patch.object(repository, "_async_install_repository", install):
        installing = hass.async_create_task(repository.async_install_repository())
        await asyncio.sleep(0)
        unloading = hass.async_create_task(
            hass.config_entries.async_unload(mock_config_entry.entry_id)
        )
        await asyncio.sleep(0)
        assert not unloading.done()

        release.set()
        await installing
        assert await unloading

    assert finished == ["install"]
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_stops_the_startup_tasks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an unload during the startup tasks leaves nothing running behind."""
    started = asyncio.Event()

    async def removed_repositories(self: MarketplaceManager, *args: Any) -> None:
        started.set()
        await asyncio.Event().wait()

    with (
        patch.object(
            MarketplaceManager,
            "async_handle_removed_repositories",
            removed_repositories,
        ),
        patch.object(
            MarketplaceManager, "async_handle_critical_repositories"
        ) as critical,
    ):
        # Not waiting for all tasks, the startup tasks never finish here
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await started.wait()
        marketplace = get_marketplace(hass)

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    critical.assert_not_called()
    assert marketplace.system.disabled


async def test_custom_repository_updates_without_custom_repositories(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test nothing waits for custom repository updates when there are none."""
    await setup_integration(hass, mock_config_entry)
    marketplace = get_marketplace(hass)

    with patch.object(
        mock_config_entry, "async_create_background_task"
    ) as create_background_task:
        await marketplace.async_update_installed_custom_repositories()

    create_background_task.assert_not_called()


@pytest.mark.usefixtures("stored_repositories")
async def test_custom_repository_update_failure_still_updates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failing custom repository update does not leave entities waiting."""
    await setup_integration(hass, mock_config_entry)
    marketplace = get_marketplace(hass)
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    with (
        patch.object(marketplace.repositories, "is_default", return_value=False),
        patch.object(
            repository, "update_repository", side_effect=MarketplaceError("boom")
        ),
        patch.object(
            marketplace.coordinators[repository.data.category],
            "async_update_listeners",
        ) as update_listeners,
    ):
        await marketplace.async_update_installed_custom_repositories()
        await marketplace.queue.execute()
        async with asyncio.timeout(5):
            await hass.async_block_till_done(wait_background_tasks=True)

    update_listeners.assert_called()


@pytest.mark.parametrize(
    ("side_effect", "state", "translation_key"),
    [
        pytest.param(
            GitHubAuthenticationException("Bad credentials"),
            ConfigEntryState.SETUP_ERROR,
            "invalid_token",
            id="authentication",
        ),
        pytest.param(
            GitHubException("GitHub is having a moment"),
            ConfigEntryState.SETUP_RETRY,
            "setup_failed",
            id="github_api",
        ),
        pytest.param(
            MarketplaceError("Something went wrong"),
            ConfigEntryState.SETUP_RETRY,
            "setup_failed",
            id="marketplace",
        ),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test a failure while setting up leaves the entry for core to handle."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(MarketplaceData, "restore", side_effect=side_effect):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is state
    assert mock_config_entry.error_reason_translation_key == translation_key


async def test_setup_fails_without_restored_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test data that can not be read is not retried, trying again changes nothing."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(MarketplaceData, "restore", return_value=False):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "restore_failed"


@pytest.mark.parametrize(
    ("reason", "state", "translation_key"),
    [
        pytest.param(
            DisabledReason.INVALID_TOKEN,
            ConfigEntryState.SETUP_ERROR,
            "invalid_token",
            id="invalid_token",
        ),
        pytest.param(
            DisabledReason.RATE_LIMIT,
            ConfigEntryState.SETUP_RETRY,
            "disabled_rate_limit",
            id="rate_limit",
        ),
        pytest.param(
            DisabledReason.REMOVED,
            ConfigEntryState.SETUP_RETRY,
            "disabled_removed",
            id="removed",
        ),
    ],
)
async def test_setup_with_a_disabled_marketplace(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    reason: DisabledReason,
    state: ConfigEntryState,
    translation_key: str,
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
    assert mock_config_entry.error_reason_translation_key == translation_key


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
async def test_entities_for_installed_repositories(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test each installed repository gets an update and a switch entity."""
    await setup_integration(hass, mock_config_entry)

    marketplace = get_marketplace(hass)
    assert {
        repo.data.full_name for repo in marketplace.repositories.list_installed
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
        "update.basic_integration",
        "update.basic_plugin",
    ]
    assert entities == snapshot(name="entities")

    assert hass.states.get("update.basic_integration") == snapshot(name="update_state")


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
    """Test removing a device for a repository that is not installed."""
    device_entry = MagicMock(spec=dr.DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = identifiers

    assert await async_remove_config_entry_device(hass, mock_config_entry, device_entry)


@pytest.mark.usefixtures("stored_repositories", "init_integration")
async def test_remove_device_still_installed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a device for an installed repository is refused."""
    device_entry = MagicMock(spec=dr.DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = {(DOMAIN, REPOSITORY_INTEGRATION_ID)}

    with pytest.raises(
        HomeAssistantError,
        match=(
            f"Cannot remove the service for {REPOSITORY_INTEGRATION}, "
            "it is still installed"
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


async def test_system_entry_created(hass: HomeAssistant) -> None:
    """Test the Marketplace sets itself up without a GitHub account."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_SYSTEM
    assert entries[0].data == {}
    assert entries[0].state is ConfigEntryState.LOADED
    assert not get_marketplace(hass).github_connected


@pytest.mark.parametrize(
    "disabled_by",
    [
        pytest.param(None, id="enabled"),
        pytest.param(ConfigEntryDisabler.USER, id="disabled"),
    ],
)
async def test_system_entry_not_created_twice(
    hass: HomeAssistant, disabled_by: ConfigEntryDisabler | None
) -> None:
    """Test an existing entry, disabled or not, is the one the Marketplace keeps."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, disabled_by=disabled_by)
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [config_entry]
    assert config_entry.disabled_by is disabled_by
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.usefixtures("stored_repositories")
async def test_setup_without_github(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test setting up without an account leaves GitHub alone."""
    # The client must not pick up a token that happens to be in the environment
    monkeypatch.setenv("GITHUB_TOKEN", "from_the_environment")

    await setup_integration(hass, mock_config_entry)

    marketplace = get_marketplace(hass)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not marketplace.github_connected
    assert not marketplace.system.disabled
    assert marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    # The background work that talks to GitHub is not scheduled, the catalog,
    # its removals and its critical repositories are
    assert len(marketplace.recurring_tasks) == 3
    await marketplace.async_update_installed_custom_repositories()
    assert not marketplace.queue.has_pending_tasks
    assert await marketplace.async_can_update() == 0

    assert not github_api_calls(aioclient_mock)

    # Anonymous calls go out without a token
    await marketplace.githubapi.rate_limit()
    _, url, _, headers = aioclient_mock.mock_calls[-1]
    assert url.host == "api.github.com"
    assert "Authorization" not in headers


@pytest.mark.parametrize("github_token", [None])
async def test_setup_authentication_failure_without_github(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test there is nothing to reauthenticate without a connected account."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        MarketplaceData,
        "restore",
        side_effect=GitHubAuthenticationException("Bad credentials"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            GitHubRatelimitException("API rate limit exceeded"),
            GitHubRateLimitError,
            id="rate_limit",
        ),
        pytest.param(
            GitHubAuthenticationException("Bad credentials"),
            MarketplaceError,
            id="authentication",
        ),
    ],
)
@pytest.mark.parametrize("github_token", [None])
async def test_anonymous_github_errors_do_not_disable(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    side_effect: Exception,
    error: type[MarketplaceError],
) -> None:
    """Test an anonymous refusal only fails the call that hit it."""
    with pytest.raises(error):
        await marketplace.async_github_api_method(AsyncMock(side_effect=side_effect))
    await hass.async_block_till_done()

    assert not marketplace.system.disabled
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(
            GitHubRatelimitException("API rate limit exceeded"),
            DisabledReason.RATE_LIMIT,
            id="rate_limit",
        ),
        pytest.param(
            GitHubAuthenticationException("Bad credentials"),
            DisabledReason.INVALID_TOKEN,
            id="authentication",
        ),
    ],
)
async def test_connected_github_errors_disable(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    side_effect: Exception,
    reason: DisabledReason,
) -> None:
    """Test a refusal of the connected account disables the Marketplace."""
    with pytest.raises(MarketplaceError):
        await marketplace.async_github_api_method(AsyncMock(side_effect=side_effect))

    assert marketplace.system.disabled_reason is reason

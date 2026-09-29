"""Tests for the Marketplace update entities."""

from http import HTTPStatus
import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.auth.models import User
from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import CONF_WARNING_ACCEPTED, DOMAIN
from homeassistant.components.marketplace.enums import (
    MarketplaceSignal,
    RepositoryCategory,
)
from homeassistant.components.marketplace.repositories.base import Repository
from homeassistant.components.marketplace.update import RepositoryUpdateEntity
from homeassistant.components.update import (
    ATTR_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.config_entries import SOURCE_SYSTEM
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import (
    CategoryTestData,
    assert_api_usage,
    category_test_data_parametrized,
    get_marketplace,
    github_api_calls,
    mocked_response,
)
from .conftest import MarketplaceResponses
from .const import REPOSITORY_INTEGRATION, REPOSITORY_INTEGRATION_ID

from tests.common import MockConfigEntry, MockUser
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture
async def installed_repository(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    category_test_data: CategoryTestData,
) -> Repository:
    """Return an installed repository with its entities loaded."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    repository.data.installed = True
    repository.data.installed_version = category_test_data["version_base"]
    # An installed repository has its files on disk
    Path(repository.localpath).mkdir(parents=True, exist_ok=True)

    await hass.config_entries.async_reload(
        marketplace.configuration.config_entry.entry_id
    )
    await hass.async_block_till_done()

    return get_marketplace(hass).repositories.get_by_full_name(
        category_test_data["repository"]
    )


@pytest.fixture
async def integration_update_entity(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    entity_registry: er.EntityRegistry,
) -> str:
    """Return the update entity of an installed integration repository."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = True
    repository.data.installed_version = "1.0.0"
    # An installed repository has its files on disk
    Path(repository.localpath).mkdir(parents=True, exist_ok=True)

    await hass.config_entries.async_reload(
        marketplace.configuration.config_entry.entry_id
    )
    await hass.async_block_till_done()

    return entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, REPOSITORY_INTEGRATION_ID
    )


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_update_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    installed_repository: Repository,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the update entity of every repository category."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, category_test_data["id"]
    )
    assert entity_id is not None

    assert entity_registry.async_get(entity_id) == snapshot(name="entry")
    assert hass.states.get(entity_id) == snapshot(name="state")


@pytest.mark.usefixtures("stored_repositories")
async def test_update_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device an installed repository is represented by."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("update.basic_integration")
    assert entity_entry is not None
    assert device_registry.async_get(entity_entry.device_id) == snapshot


async def test_update_entity_becomes_unavailable(
    hass: HomeAssistant, marketplace: MarketplaceManager, integration_update_entity: str
) -> None:
    """Test that removing a repository makes its update entity unavailable."""
    assert hass.states.get(integration_update_entity).state == "off"

    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = False
    repository.data.last_fetched = None
    get_marketplace(hass).coordinators[
        repository.data.category
    ].async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(integration_update_entity).state == "unavailable"


async def test_update_entity_picture(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test that an integration is pictured by its brand icon."""
    state = hass.states.get(integration_update_entity)

    assert (
        state.attributes["entity_picture"] == "/api/brands/integration/example/icon.png"
    )


@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(categories=["plugin"]),
)
@pytest.mark.usefixtures("installed_repository")
async def test_update_entity_picture_for_other_categories(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    category_test_data: CategoryTestData,
) -> None:
    """Test that only integrations get a brand icon."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, category_test_data["id"]
    )

    assert "entity_picture" not in hass.states.get(entity_id).attributes


async def test_update_entity_release_summary(
    hass: HomeAssistant, marketplace: MarketplaceManager, integration_update_entity: str
) -> None:
    """Test a pending restart is left to the translated repair issue."""
    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.pending_restart = True
    repository.data.last_fetched = None
    get_marketplace(hass).coordinators[
        repository.data.category
    ].async_update_listeners()
    await hass.async_block_till_done()

    assert (
        hass.states.get(integration_update_entity).attributes["release_summary"] is None
    )


async def test_update_entity_install_progress(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test that an install reports its progress on the update entity."""
    assert hass.states.get(integration_update_entity).attributes["in_progress"] is False

    async_dispatcher_send(
        hass,
        MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
        {"repository": REPOSITORY_INTEGRATION, "progress": 40},
    )
    await hass.async_block_till_done()

    attributes = hass.states.get(integration_update_entity).attributes
    assert attributes["in_progress"] is True
    assert attributes["update_percentage"] == 40

    async_dispatcher_send(
        hass,
        MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
        {"repository": REPOSITORY_INTEGRATION, "progress": False},
    )
    await hass.async_block_till_done()

    attributes = hass.states.get(integration_update_entity).attributes
    assert attributes["in_progress"] is False
    assert attributes["update_percentage"] is None


async def test_update_entity_ignores_other_repositories(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test that the progress of another install is ignored."""
    async_dispatcher_send(
        hass,
        MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS,
        {"repository": "other/repository", "progress": 40},
    )
    await hass.async_block_till_done()

    assert hass.states.get(integration_update_entity).attributes["in_progress"] is False


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_install(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entity_registry: er.EntityRegistry,
    installed_repository: Repository,
    category_test_data: CategoryTestData,
) -> None:
    """Test installing a specific version through the update entity."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, category_test_data["id"]
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VERSION: category_test_data["version_update"],
        },
        blocking=True,
    )

    assert (
        installed_repository.data.installed_version
        == category_test_data["version_update"]
    )

    # Stored right away, a restart before the next write keeps the new version
    stored = hass_storage[f"{DOMAIN}.repositories"]["data"][category_test_data["id"]]
    assert stored["version_installed"] == category_test_data["version_update"]


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_install_update_from_the_catalog(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    installed_repository: Repository,
    aioclient_mock: AiohttpClientMocker,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test installing the update the catalog announces skips the GitHub API."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, category_test_data["id"]
    )
    installed_repository.data.last_version = category_test_data["version_update"]
    aioclient_mock.mock_calls.clear()

    await hass.services.async_call(
        UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert (
        installed_repository.data.installed_version
        == category_test_data["version_update"]
    )
    assert not github_api_calls(aioclient_mock)
    assert_api_usage(aioclient_mock, snapshot)

    state = hass.states.get(entity_id)
    assert state.attributes["installed_version"] == category_test_data["version_update"]
    assert state.attributes["latest_version"] == category_test_data["version_update"]


@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(categories=[RepositoryCategory.INTEGRATION]),
)
async def test_install_newest_commit_of_a_custom_repository(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    installed_repository: Repository,
    aioclient_mock: AiohttpClientMocker,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
    category_test_data: CategoryTestData,
) -> None:
    """Test a repository without releases updates to what its branch holds."""
    branch_archive = (
        "https://github.com/hacs-test-org/integration-basic/archive/refs/heads/main.zip"
    )
    recorded = Path(__file__).parent.joinpath(
        "fixtures/proxy/github.com/hacs-test-org/integration-basic"
        "/archive/refs/tags/1.0.0.zip"
    )
    response_mocker.add(
        branch_archive, mocked_response(branch_archive, content=recorded.read_bytes())
    )
    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, category_test_data["id"]
    )
    marketplace = get_marketplace(hass)
    data = installed_repository.data
    data.releases = False
    data.last_version = None
    data.installed_version = None
    data.installed_commit = "1234abc"
    data.last_commit = "7fd1a60"
    data.default_branch = "main"
    # What the patched update_repository resolves the content to
    installed_repository.content.path.remote = "custom_components/example"
    aioclient_mock.mock_calls.clear()

    with (
        patch.object(marketplace.repositories, "is_default", return_value=False),
        patch.object(installed_repository, "update_repository"),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

    requested = [str(call[1]) for call in aioclient_mock.mock_calls]
    assert not [url for url in requested if "7fd1a60" in url]
    assert branch_archive in requested
    assert data.installed_commit == "7fd1a60"
    assert data.installed_version is None


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_install_update_of_a_custom_repository(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    installed_repository: Repository,
    aioclient_mock: AiohttpClientMocker,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test an update of a repository outside the catalog uses the GitHub API."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, category_test_data["id"]
    )
    marketplace = get_marketplace(hass)
    installed_repository.data.last_version = category_test_data["version_update"]
    aioclient_mock.mock_calls.clear()

    with patch.object(marketplace.repositories, "is_default", return_value=False):
        await hass.services.async_call(
            UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

    assert (
        installed_repository.data.installed_version
        == category_test_data["version_update"]
    )
    assert github_api_calls(aioclient_mock)
    assert_api_usage(aioclient_mock, snapshot)


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(categories=[RepositoryCategory.TEMPLATE]),
)
async def test_template_update_writes_only_the_template(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    installed_repository: Repository,
    category_test_data: CategoryTestData,
) -> None:
    """Test a template update writes its file, not the rest of the repository."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, category_test_data["id"]
    )
    installed_repository.data.last_version = category_test_data["version_update"]
    # Stored before template file names were
    installed_repository.data.file_name = ""

    with patch.object(
        get_marketplace(hass).repositories, "is_default", return_value=False
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

    assert sorted(
        path.name for path in Path(installed_repository.localpath).iterdir()
    ) == ["example.jinja"]


async def test_install_already_installed_version(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test installing the version that is already there."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Version 1.0.0 of {REPOSITORY_INTEGRATION} is already installed"
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "1.0.0"},
            blocking=True,
        )


async def test_install_refuses_a_version_that_is_a_path(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test the version of an install can not point at another repository."""
    with pytest.raises(ServiceValidationError, match="not a version"):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: integration_update_entity,
                ATTR_VERSION: "../../other/repo/archive/refs/heads/main",
            },
            blocking=True,
        )


async def test_install_without_an_update(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test installing when the installed version is the latest one."""
    with pytest.raises(
        HomeAssistantError,
        match=f"No update available for {integration_update_entity}",
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity},
            blocking=True,
        )


async def test_install_version_without_a_manifest(
    hass: HomeAssistant,
    integration_update_entity: str,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test installing a version that carries no hacs.json."""
    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/3.0.0/hacs.json"
    response_mocker.add(
        url, mocked_response(url, status=HTTPStatus.NOT_FOUND), keep=True
    )

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Installing {REPOSITORY_INTEGRATION} failed: Version 3.0.0 of "
            f"{REPOSITORY_INTEGRATION} has no hacs.json, which installing needs"
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "3.0.0"},
            blocking=True,
        )


async def test_install_version_requiring_a_newer_core(
    hass: HomeAssistant,
    integration_update_entity: str,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test installing a version that needs a newer Home Assistant."""
    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/3.0.0/hacs.json"
    response_mocker.add(
        url,
        mocked_response(
            url, content=json.dumps({"homeassistant": "9999.99.99"}).encode()
        ),
        keep=True,
    )

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Installing {REPOSITORY_INTEGRATION} failed: This version requires "
            "Home Assistant 9999.99.99 or newer."
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "3.0.0"},
            blocking=True,
        )


async def test_install_download_failure(
    hass: HomeAssistant,
    integration_update_entity: str,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test a version that can not be downloaded."""
    for url in (
        f"https://github.com/{REPOSITORY_INTEGRATION}/archive/refs/tags/2.0.0.zip",
        f"https://github.com/{REPOSITORY_INTEGRATION}/archive/refs/heads/2.0.0.zip",
        # The file by file download that follows a failed archive
        f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/1.0.0"
        "/custom_components/example/manifest.json",
    ):
        response_mocker.add(
            url,
            mocked_response(url, status=HTTPStatus.SERVICE_UNAVAILABLE),
            keep=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Installing {REPOSITORY_INTEGRATION} failed: Installing "
            f"{REPOSITORY_INTEGRATION} with version 2.0.0 failed with "
            "(Could not install, see log for details)"
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "2.0.0"},
            blocking=True,
        )


async def test_release_notes(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    integration_update_entity: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the release notes shown for an available update."""
    repository = get_marketplace(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed_version = "0.9.0"

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "update/release_notes", "entity_id": integration_update_entity}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == snapshot


async def test_release_notes_while_pending_restart(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    integration_update_entity: str,
) -> None:
    """Test that a repository waiting for a restart has no release notes."""
    get_marketplace(hass).repositories.get_by_id(
        REPOSITORY_INTEGRATION_ID
    ).pending_restart = True

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "update/release_notes", "entity_id": integration_update_entity}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] is None


@pytest.mark.parametrize("github_token", [None])
async def test_install_without_github(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test installing an update works without a GitHub connection."""
    marketplace = get_marketplace(hass)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "2.0.0"},
        blocking=True,
    )

    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert repository.data.installed_version == "2.0.0"
    assert not marketplace.system.disabled


@pytest.mark.parametrize("config_entry_source", [SOURCE_SYSTEM])
@pytest.mark.parametrize("warning_accepted", [None])
async def test_install_needs_accepted_warning(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    integration_update_entity: str,
) -> None:
    """Test an install without a user is refused until someone accepts the warning."""
    marketplace = get_marketplace(hass)
    assert CONF_WARNING_ACCEPTED not in marketplace.configuration.config_entry.data

    with pytest.raises(
        HomeAssistantError,
        match="Open the Marketplace and read the warning first",
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "2.0.0"},
            blocking=True,
        )

    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert repository.data.installed_version == "1.0.0"

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "marketplace/warning/accept"})
    assert (await client.receive_json())["success"]

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "2.0.0"},
        blocking=True,
    )

    assert repository.data.installed_version == "2.0.0"


async def test_install_needs_warning_accepted_by_caller(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    second_admin_user: User,
    integration_update_entity: str,
) -> None:
    """Test a user installing an update needs to have accepted the warning."""
    marketplace = get_marketplace(hass)
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)

    with pytest.raises(
        HomeAssistantError,
        match="Open the Marketplace and read the warning first",
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "2.0.0"},
            blocking=True,
            context=Context(user_id=second_admin_user.id),
        )

    assert repository.data.installed_version == "1.0.0"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "2.0.0"},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert repository.data.installed_version == "2.0.0"


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(HTTPStatus.FORBIDDEN, id="403"),
        pytest.param(HTTPStatus.TOO_MANY_REQUESTS, id="429"),
    ],
)
@pytest.mark.parametrize("github_token", [None])
async def test_install_rate_limited_without_github(
    hass: HomeAssistant,
    integration_update_entity: str,
    response_mocker: MarketplaceResponses,
    status: HTTPStatus,
) -> None:
    """Test running out of anonymous requests fails the install clearly."""
    marketplace = get_marketplace(hass)
    url = f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}"
    response_mocker.add(
        url,
        mocked_response(
            url,
            status=status,
            json_content={"message": "API rate limit exceeded for 127.0.0.1."},
        ),
        keep=True,
    )

    with pytest.raises(
        HomeAssistantError,
        match=(
            "GitHub limits how often the Marketplace can reach it without a "
            "GitHub connection"
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "2.0.0"},
            blocking=True,
        )
    await hass.async_block_till_done()

    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert repository.data.installed_version == "1.0.0"
    assert not marketplace.system.disabled
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize("github_token", [None])
async def test_latest_version_without_github(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test the latest version comes from the catalog without an account."""
    state = hass.states.get(integration_update_entity)

    assert state.attributes["installed_version"] == "1.0.0"
    assert state.attributes["latest_version"] == "1.0.0"


@pytest.mark.parametrize("github_token", [None])
async def test_release_notes_rate_limited_without_github(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    integration_update_entity: str,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test the release notes fall back to what is known when rate limited."""
    marketplace = get_marketplace(hass)
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.published_tags = []

    url = f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}/releases"
    response_mocker.add(
        url,
        mocked_response(
            url,
            status=HTTPStatus.FORBIDDEN,
            json_content={"message": "API rate limit exceeded for 127.0.0.1."},
        ),
    )
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "update/release_notes", "entity_id": integration_update_entity}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == ""
    assert not marketplace.system.disabled


def test_release_url_points_at_the_release(marketplace: MarketplaceManager) -> None:
    """Test the link goes to the page of the release, not the release list."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.releases = True
    repository.data.last_version = "2.0.0"
    entity = RepositoryUpdateEntity(marketplace, repository)

    assert entity.release_url == (
        f"https://github.com/{REPOSITORY_INTEGRATION}/releases/tag/2.0.0"
    )

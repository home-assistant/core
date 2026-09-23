"""Tests for the Marketplace update entities."""

from http import HTTPStatus
import json
from pathlib import Path
import re

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.marketplace.base import StoreManager
from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.components.marketplace.enums import StoreSignal
from homeassistant.components.marketplace.repositories.base import Repository
from homeassistant.components.update import (
    ATTR_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from . import (
    CategoryTestData,
    category_test_data_parametrized,
    get_store,
    mocked_response,
)
from .conftest import StoreResponses
from .const import REPOSITORY_INTEGRATION, REPOSITORY_INTEGRATION_ID

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def python_script_integration(hass: HomeAssistant, config_dir: Path) -> None:
    """Load the python script integration so its category is active."""
    (config_dir / "python_scripts").mkdir()
    assert await async_setup_component(hass, "python_script", {})


@pytest.fixture
async def downloaded_repository(
    hass: HomeAssistant, store: StoreManager, category_test_data: CategoryTestData
) -> Repository:
    """Return a downloaded repository with its entities loaded."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
    repository.data.installed = True
    repository.data.installed_version = category_test_data["version_base"]

    await hass.config_entries.async_reload(store.configuration.config_entry.entry_id)
    await hass.async_block_till_done()

    return get_store(hass).repositories.get_by_full_name(
        category_test_data["repository"]
    )


@pytest.fixture
async def integration_update_entity(
    hass: HomeAssistant, store: StoreManager, entity_registry: er.EntityRegistry
) -> str:
    """Return the update entity of a downloaded integration repository."""
    repository = store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = True
    repository.data.installed_version = "1.0.0"

    await hass.config_entries.async_reload(store.configuration.config_entry.entry_id)
    await hass.async_block_till_done()

    return entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, REPOSITORY_INTEGRATION_ID
    )


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_update_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    downloaded_repository: Repository,
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
    """Test the device a downloaded repository is represented by."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("update.basic_integration_update")
    assert entity_entry is not None
    assert device_registry.async_get(entity_entry.device_id) == snapshot


async def test_update_entity_becomes_unavailable(
    hass: HomeAssistant, store: StoreManager, integration_update_entity: str
) -> None:
    """Test that removing a repository makes its update entity unavailable."""
    assert hass.states.get(integration_update_entity).state == "off"

    repository = get_store(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = False
    repository.data.last_fetched = None
    get_store(hass).coordinators[repository.data.category].async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(integration_update_entity).state == "unavailable"


async def test_update_entity_picture(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test that an integration is pictured by its brand icon."""
    state = hass.states.get(integration_update_entity)

    assert (
        state.attributes["entity_picture"]
        == "https://brands.home-assistant.io/_/example/icon.png"
    )


@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(categories=["plugin"]),
)
@pytest.mark.usefixtures("downloaded_repository")
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
    hass: HomeAssistant, store: StoreManager, integration_update_entity: str
) -> None:
    """Test that a repository waiting for a restart says so."""
    repository = get_store(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.pending_restart = True
    repository.data.last_fetched = None
    get_store(hass).coordinators[repository.data.category].async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(integration_update_entity).attributes["release_summary"] == (
        "<ha-alert alert-type='error'>Restart of Home Assistant required</ha-alert>"
    )


async def test_update_entity_download_progress(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test that a download reports its progress on the update entity."""
    assert hass.states.get(integration_update_entity).attributes["in_progress"] is False

    async_dispatcher_send(
        hass,
        StoreSignal.REPOSITORY_DOWNLOAD_PROGRESS,
        {"repository": REPOSITORY_INTEGRATION, "progress": 40},
    )
    await hass.async_block_till_done()

    attributes = hass.states.get(integration_update_entity).attributes
    assert attributes["in_progress"] is True
    assert attributes["update_percentage"] == 40

    async_dispatcher_send(
        hass,
        StoreSignal.REPOSITORY_DOWNLOAD_PROGRESS,
        {"repository": REPOSITORY_INTEGRATION, "progress": False},
    )
    await hass.async_block_till_done()

    attributes = hass.states.get(integration_update_entity).attributes
    assert attributes["in_progress"] is False
    assert attributes["update_percentage"] is None


async def test_update_entity_ignores_other_repositories(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test that the progress of another download is ignored."""
    async_dispatcher_send(
        hass,
        StoreSignal.REPOSITORY_DOWNLOAD_PROGRESS,
        {"repository": "other/repository", "progress": 40},
    )
    await hass.async_block_till_done()

    assert hass.states.get(integration_update_entity).attributes["in_progress"] is False


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_install(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    downloaded_repository: Repository,
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
        downloaded_repository.data.installed_version
        == category_test_data["version_update"]
    )


async def test_install_already_downloaded_version(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test installing the version that is already there."""
    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Version 1.0.0 of {REPOSITORY_INTEGRATION} is already downloaded"
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: integration_update_entity, ATTR_VERSION: "1.0.0"},
            blocking=True,
        )


async def test_install_without_an_update(
    hass: HomeAssistant, integration_update_entity: str
) -> None:
    """Test installing when the downloaded version is the latest one."""
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
    response_mocker: StoreResponses,
) -> None:
    """Test installing a version that carries no hacs.json."""
    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/3.0.0/hacs.json"
    response_mocker.add(
        url, mocked_response(url, status=HTTPStatus.NOT_FOUND), keep=True
    )

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Downloading {REPOSITORY_INTEGRATION} failed: The version 3.0.0 "
            "for this integration can not be used."
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
    response_mocker: StoreResponses,
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
            f"Downloading {REPOSITORY_INTEGRATION} failed: This version requires "
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
    response_mocker: StoreResponses,
) -> None:
    """Test a version that can not be downloaded."""
    for variant in ("tags", "heads"):
        url = (
            f"https://github.com/{REPOSITORY_INTEGRATION}"
            f"/archive/refs/{variant}/2.0.0.zip"
        )
        response_mocker.add(
            url,
            mocked_response(url, status=HTTPStatus.SERVICE_UNAVAILABLE),
            keep=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match=re.escape(
            f"Downloading {REPOSITORY_INTEGRATION} failed: Downloading "
            f"{REPOSITORY_INTEGRATION} with version 2.0.0 failed with "
            "(Could not download, see log for details)"
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
    repository = get_store(hass).repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
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
    get_store(hass).repositories.get_by_id(
        REPOSITORY_INTEGRATION_ID
    ).pending_restart = True

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "update/release_notes", "entity_id": integration_update_entity}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] is None

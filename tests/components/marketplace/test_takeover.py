"""Test taking over a real HACS install, from the first boot to the second.

The fixtures in hacs_install are what the HACS custom integration wrote after
installing an integration, a plugin and a theme: its storage files, its config
entry and the registries, in the storage versions of that Home Assistant.
"""

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import bootstrap, config_entries
from homeassistant.components.lovelace import LOVELACE_DATA
from homeassistant.components.marketplace.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
    storage,
)
from homeassistant.helpers.json import json_dumps
from homeassistant.setup import async_setup_component

from tests.common import flush_store, load_json_object_fixture

HACS_FILES = ("hacs.repositories", "hacs.hacs", "hacs.data")
REGISTRY_KEYS = (
    "core.config_entries",
    "core.entity_registry",
    "core.device_registry",
    "lovelace_resources",
)

INTEGRATION_ID = "1296269"
PLUGIN_ID = "1296267"
THEME_ID = "1296266"
APPDAEMON_ID = "1296265"
HACS_ID = "172733314"

RENAMED_ENTITY_ID = "update.my_example_integration"


def _customize(install: dict[str, Any]) -> None:
    """Change the registries the way a user would have over the years."""
    entities = {
        entity["unique_id"]: entity
        for entity in install["core.entity_registry"]["data"]["entities"]
    }
    entities[INTEGRATION_ID] |= {
        "entity_id": RENAMED_ENTITY_ID,
        "name": "My example integration",
    }
    entities[PLUGIN_ID] |= {"disabled_by": "user"}
    entities[THEME_ID] |= {"hidden_by": "user", "labels": ["favorites"]}

    for device in install["core.device_registry"]["data"]["devices"]:
        if device["identifiers"] == [["hacs", INTEGRATION_ID]]:
            device |= {"name_by_user": "Example", "area_id": "office"}


@pytest.fixture
def hacs_install(config_dir: Path, hass_storage: dict[str, Any]) -> dict[str, Any]:
    """Leave behind what a HACS install has, on disk and in storage."""
    install = load_json_object_fixture("hacs_install/install.json", DOMAIN)
    _customize(install)

    for key in REGISTRY_KEYS:
        hass_storage[key] = install[key]

    storage_path = config_dir / storage.STORAGE_DIR
    storage_path.mkdir(exist_ok=True)
    for name in HACS_FILES:
        (storage_path / name).write_text(
            json.dumps(load_json_object_fixture(f"hacs_install/{name}.json", DOMAIN)),
            encoding="utf-8",
        )

    for path, content in install["files"].items():
        (config_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (config_dir / path).write_text(content, encoding="utf-8")

    manifest = config_dir / "custom_components" / "hacs" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(install["custom_components/hacs/manifest.json"]), encoding="utf-8"
    )

    return install


@pytest.fixture
def marketplace_files_on_disk() -> Generator[None]:
    """Let the Marketplace storage reach the disk, like it does outside tests.

    The files HACS left are only removed once the Marketplace has written its
    own, and the storage mock of the tests keeps every write in memory.
    """
    mocked_write = storage.Store._async_write_data

    async def write_data(store: storage.Store, data: dict[str, Any]) -> None:
        await mocked_write(store, data)
        if store.key.startswith(f"{DOMAIN}."):
            path = Path(store.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_dumps(data), encoding="utf-8")

    with patch.object(storage.Store, "_async_write_data", write_data):
        yield


async def _async_load_storage(hass: HomeAssistant) -> None:
    """Load the registries and config entries from storage, like a boot does."""
    await bootstrap.async_load_base_functionality(hass)

    # The manager of the test instance never read the storage
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()


async def _async_boot(hass: HomeAssistant) -> str:
    """Boot from storage and set up the Marketplace entry."""
    await _async_load_storage(hass)

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.entry_id


def _platforms(hass: HomeAssistant, entry_id: str) -> set[str]:
    """Return the platforms of the entities of the entry."""
    return {
        entity.platform
        for entity in er.async_entries_for_config_entry(er.async_get(hass), entry_id)
    }


def _registries(
    hass: HomeAssistant, entry_id: str, known_entity_ids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return what the takeover changes in the registries, device ids replaced.

    Entities created after the takeover get their entity id in whatever order
    the platforms set up, only those HACS had are worth pinning.
    """
    device_registry = dr.async_get(hass)
    devices = sorted(
        dr.async_entries_for_config_entry(device_registry, entry_id),
        key=lambda device: sorted(device.identifiers),
    )
    device_names = {
        device.id: f"device {index}" for index, device in enumerate(devices)
    }

    return (
        [
            {
                "entity_id": (
                    entity.entity_id
                    if entity.entity_id in known_entity_ids
                    else f"new {entity.domain}"
                ),
                "platform": entity.platform,
                "unique_id": entity.unique_id,
                "device": device_names.get(entity.device_id),
                "name": entity.name,
                "disabled_by": entity.disabled_by,
                "hidden_by": entity.hidden_by,
                "labels": sorted(entity.labels),
            }
            for entity in sorted(
                er.async_entries_for_config_entry(er.async_get(hass), entry_id),
                key=lambda entity: (entity.unique_id, entity.domain),
            )
        ],
        [
            {
                "device": device_names[device.id],
                "identifiers": sorted(device.identifiers),
                "name": device.name,
                "name_by_user": device.name_by_user,
                "area_id": device.area_id,
                "configuration_url": device.configuration_url,
            }
            for device in devices
        ],
    )


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("marketplace_files_on_disk")
async def test_takeover_of_a_hacs_install(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hacs_install: dict[str, Any],
    config_dir: Path,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the first boot takes over everything and the second changes nothing."""
    (hacs_entry,) = hacs_install["core.config_entries"]["data"]["entries"]
    known_entity_ids = {
        entity["entity_id"]
        for entity in hacs_install["core.entity_registry"]["data"]["entities"]
    }

    entry_id = await _async_boot(hass)
    entry = hass.config_entries.async_get_entry(entry_id)

    # The entry of HACS itself, converted in place
    assert entry.entry_id == hacs_entry["entry_id"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == hacs_entry["data"]
    assert entry.options == {}
    await flush_store(hass.config_entries._store)
    (stored_entry,) = hass_storage["core.config_entries"]["data"]["entries"]
    assert stored_entry["domain"] == DOMAIN

    # Entities and devices keep what the user did to them, HACS itself is gone
    assert _registries(hass, entry_id, known_entity_ids) == snapshot(name="registries")

    # The installed repositories carry over, what the Marketplace does not
    # manage does not
    marketplace = entry.runtime_data
    assert {
        repository.data.id for repository in marketplace.repositories.list_installed
    } == {INTEGRATION_ID, PLUGIN_ID, THEME_ID}
    assert marketplace.repositories.get_by_id(APPDAEMON_ID) is None
    assert marketplace.repositories.get_by_id(HACS_ID) is None

    # The dashboard resource points at the new location
    assert [
        resource["url"] for resource in hass.data[LOVELACE_DATA].resources.async_items()
    ] == ["/local/community/plugin-basic/plugin-basic.js?v=1296267100"]

    # What HACS left on disk is gone, the installed repositories are not
    for name in HACS_FILES:
        assert not (config_dir / storage.STORAGE_DIR / name).exists()
    assert not (config_dir / "custom_components" / "hacs").exists()
    for path in hacs_install["files"]:
        assert (config_dir / path).exists()

    # The registries load from storage in this test, after the fixtures run
    assert not [
        issue_id
        for domain, issue_id in ir.async_get(hass).issues  # pylint: disable=home-assistant-tests-registry-fixtures
        if domain == "hacs" or issue_id == "integration_not_found.hacs"
    ]

    # A second boot finds nothing left to take over
    before = _registries(hass, entry_id, known_entity_ids)
    assert await hass.config_entries.async_reload(entry_id)
    await hass.async_block_till_done()
    assert _registries(hass, entry_id, known_entity_ids) == before

    # Unloading writes the data, from then on it is the Marketplace's own
    assert await hass.config_entries.async_unload(entry_id)
    await hass.async_block_till_done()
    repositories = hass_storage[f"{DOMAIN}.repositories"]["data"]
    assert {
        repository_id
        for repository_id, repository in repositories.items()
        if repository.get("installed")
    } == {INTEGRATION_ID, PLUGIN_ID, THEME_ID}
    assert APPDAEMON_ID not in repositories
    assert HACS_ID not in repositories


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("marketplace_files_on_disk")
async def test_takeover_waits_for_a_disabled_entry(
    hass: HomeAssistant, hacs_install: dict[str, Any], config_dir: Path
) -> None:
    """Test a HACS entry the user disabled is only taken over once enabled."""
    (hacs_entry,) = hacs_install["core.config_entries"]["data"]["entries"]
    hacs_entry["disabled_by"] = "user"

    await _async_load_storage(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.disabled_by is ConfigEntryDisabler.USER
    assert entry.state is ConfigEntryState.NOT_LOADED
    # The disabled entry counts, no new one is started next to it
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    # Nothing is touched while the user keeps it disabled
    assert _platforms(hass, entry.entry_id) == {"hacs"}
    assert (config_dir / "custom_components" / "hacs").exists()
    for name in HACS_FILES:
        assert (config_dir / storage.STORAGE_DIR / name).exists()

    assert await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert _platforms(hass, entry.entry_id) == {DOMAIN}
    assert not (config_dir / "custom_components" / "hacs").exists()
    for name in HACS_FILES:
        assert not (config_dir / storage.STORAGE_DIR / name).exists()

    assert await hass.config_entries.async_unload(entry.entry_id)

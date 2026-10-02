"""Tests for the Marketplace storage handlers."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.marketplace.const import DOMAIN, STORAGE_VERSION
from homeassistant.components.marketplace.utils.storage import (
    STORAGE_CACHE_KEY,
    async_load_from_storage,
    async_save_to_storage,
    get_storage_for_key,
)
from homeassistant.core import HomeAssistant

from . import create_install_folders, get_marketplace, setup_integration
from .const import REPOSITORY_INTEGRATION, REPOSITORY_PLUGIN

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_object_fixture,
)

HACS_COMMON = {
    "archived_repositories": ["hacs-test-org/archived"],
    "ignored_repositories": ["hacs-test-org/ignored"],
    "renamed_repositories": {"hacs-test-org/old": "hacs-test-org/new"},
}

HACS_CRITICAL = [
    {
        "acknowledged": True,
        "link": "https://github.com/hacs-test-org/critical",
        "reason": "Bad things",
        "repository": "hacs-test-org/critical",
    }
]


def _stored(data: Any) -> dict[str, Any]:
    """Wrap data the way the storage helper writes it to disk."""
    return {"version": STORAGE_VERSION, "data": data}


def _write_hacs_file(config_dir: Path, key: str, data: Any, version: Any = "6") -> None:
    """Write a storage file the way the custom integration left it on disk."""
    storage = config_dir / ".storage"
    storage.mkdir(exist_ok=True)
    (storage / key).write_text(
        json.dumps({"version": version, "key": key, "data": data}), encoding="utf-8"
    )


@pytest.fixture
def hacs_repositories() -> dict[str, Any]:
    """Return the repository data HACS left behind."""
    return load_json_object_fixture("stored_repositories.json", DOMAIN)


@pytest.fixture
def hacs_storage(
    hass_storage: dict[str, Any],
    hacs_repositories: dict[str, Any],
    config_dir: Path,
) -> dict[str, Any]:
    """Leave the files HACS wrote on disk, with the string version it used."""
    _write_hacs_file(config_dir, "hacs.repositories", hacs_repositories)
    create_install_folders(config_dir, hacs_repositories)
    _write_hacs_file(config_dir, "hacs.hacs", HACS_COMMON)
    _write_hacs_file(config_dir, "hacs.critical", HACS_CRITICAL)
    return hass_storage


async def test_encoded_off_the_event_loop(hass: HomeAssistant) -> None:
    """Test the stores encode their data in the executor, the files are large."""
    assert get_storage_for_key(hass, "repositories")._serialize_in_event_loop is False


async def test_load(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test loading a store."""
    hass_storage["marketplace.test"] = _stored({"test": "test"})

    assert await async_load_from_storage(hass, "test") == {"test": "test"}


async def test_load_missing(hass: HomeAssistant) -> None:
    """Test loading a store without a file of its own."""
    assert await async_load_from_storage(hass, "test") == {}


async def test_save_skips_unchanged_content(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test saving the same content again does not write."""
    hass_storage["marketplace.test"] = _stored({"test": "test"})

    with patch(
        "homeassistant.helpers.storage.Store.async_save",
        return_value=AsyncMock(),
    ) as async_save_mock:
        await async_save_to_storage(hass, "test", {"test": "test"})
        assert not async_save_mock.called
        assert "Did not store data for 'marketplace.test'" in caplog.text

        await async_save_to_storage(hass, "test", {"test": "other"})
        assert async_save_mock.call_count == 1


async def test_instance_cached_per_key(hass: HomeAssistant) -> None:
    """Repeated calls for the same key must return the same Store instance.

    Store.async_delay_save() debounces via instance state, so callers that
    schedule delayed writes need the same Store object each time.
    """
    assert get_storage_for_key(hass, "test") is get_storage_for_key(hass, "test")
    assert get_storage_for_key(hass, "test") is not get_storage_for_key(hass, "other")


async def test_cache_cleared_on_unload(hass: HomeAssistant) -> None:
    """Clearing STORAGE_CACHE_KEY (as async_unload_entry does) drops cached Stores."""
    first = get_storage_for_key(hass, "test")
    hass.data.pop(STORAGE_CACHE_KEY, None)
    assert get_storage_for_key(hass, "test") is not first


async def test_hacs_data_is_adopted(
    hass: HomeAssistant,
    hacs_storage: dict[str, Any],
    hacs_repositories: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the HACS files are copied to our own keys on the first load."""
    await setup_integration(hass, mock_config_entry)

    assert hacs_storage["marketplace.repositories"] == {
        **_stored(hacs_repositories),
        "key": "marketplace.repositories",
        "minor_version": 1,
    }
    assert hacs_storage["marketplace.common"]["version"] == STORAGE_VERSION
    assert hacs_storage["marketplace.common"]["data"] == HACS_COMMON
    assert hacs_storage["marketplace.critical"]["version"] == STORAGE_VERSION
    assert hacs_storage["marketplace.critical"]["data"] == HACS_CRITICAL

    marketplace = get_marketplace(hass)
    assert {
        repo.data.full_name for repo in marketplace.repositories.list_installed
    } == {
        REPOSITORY_INTEGRATION,
        REPOSITORY_PLUGIN,
    }
    assert marketplace.common.archived_repositories == {"hacs-test-org/archived"}
    assert marketplace.common.ignored_repositories == {"hacs-test-org/ignored"}
    assert marketplace.common.renamed_repositories == {
        "hacs-test-org/old": "hacs-test-org/new"
    }


@pytest.mark.parametrize(
    "repositories",
    [
        pytest.param(None, id="no_repositories_file"),
        pytest.param({}, id="empty_repositories_file"),
    ],
)
async def test_hacs_data_is_adopted_as_fallback(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_dir: Path,
    mock_config_entry: MockConfigEntry,
    repositories: dict[str, Any] | None,
) -> None:
    """Test the older combined file is read when HACS kept its repositories there."""
    # What the custom integration itself falls back to
    hacs_data = await async_load_json_object_fixture(
        hass, "hacs_install/hacs.data.json", DOMAIN
    )
    _write_hacs_file(config_dir, "hacs.data", hacs_data["data"])
    create_install_folders(
        config_dir,
        {
            entry["id"]: {"category": category, **entry}
            for category, entries in hacs_data["data"]["repositories"].items()
            for entry in entries
        },
    )
    if repositories is not None:
        _write_hacs_file(config_dir, "hacs.repositories", repositories)

    await setup_integration(hass, mock_config_entry)

    adopted = hass_storage["marketplace.repositories"]["data"]
    assert {
        repository_id
        for repository_id, repository in adopted.items()
        if repository.get("installed")
    } == {"1296266", "1296267", "1296269", "172733314"}
    assert adopted["1296269"]["category"] == "integration"

    marketplace = get_marketplace(hass)
    assert {
        repository.data.full_name
        for repository in marketplace.repositories.list_installed
    } == {
        "hacs-test-org/integration-basic",
        "hacs-test-org/plugin-basic",
        "hacs-test-org/theme-basic",
    }


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param({"version": 1, "data": HACS_COMMON}, id="unknown_version"),
        pytest.param(["not", "a", "storage", "file"], id="not_a_storage_file"),
    ],
)
async def test_hacs_file_of_another_format_not_adopted(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config_dir: Path,
    contents: Any,
) -> None:
    """Test only a file in the format the custom integration wrote is adopted."""
    storage = config_dir / ".storage"
    storage.mkdir()
    (storage / "hacs.hacs").write_text(json.dumps(contents), encoding="utf-8")

    assert await async_load_from_storage(hass, "common") == {}
    assert "marketplace.common" not in hass_storage


async def test_own_data_wins(
    hass: HomeAssistant,
    hacs_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the HACS files are ignored once we have files of our own."""
    hacs_storage["marketplace.repositories"] = _stored(
        {
            "1296269": {
                "category": "integration",
                "full_name": REPOSITORY_INTEGRATION,
                "installed": False,
            }
        }
    )
    hacs_storage["marketplace.common"] = _stored({})

    await setup_integration(hass, mock_config_entry)

    assert not get_marketplace(hass).repositories.list_installed
    assert not get_marketplace(hass).common.archived_repositories


@pytest.mark.usefixtures("hass_storage")
async def test_fresh_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an installation without any stored data at all."""
    await setup_integration(hass, mock_config_entry)

    marketplace = get_marketplace(hass)
    assert marketplace.status.new is True
    assert not marketplace.repositories.list_installed

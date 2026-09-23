"""Tests for the Marketplace storage handlers."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.marketplace.const import DOMAIN, VERSION_STORAGE
from homeassistant.components.marketplace.exceptions import StoreError
from homeassistant.components.marketplace.utils.storage import (
    STORAGE_CACHE_KEY,
    async_load_from_storage,
    async_remove_storage,
    async_save_to_storage,
    get_storage_for_key,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import get_store, setup_integration
from .const import REPOSITORY_INTEGRATION, REPOSITORY_PLUGIN

from tests.common import MockConfigEntry, load_json_object_fixture

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
    return {"version": VERSION_STORAGE, "data": data}


@pytest.fixture
def hacs_repositories() -> dict[str, Any]:
    """Return the repository data HACS left behind."""
    return load_json_object_fixture("stored_repositories.json", DOMAIN)


@pytest.fixture
def hacs_storage(
    hass_storage: dict[str, Any], hacs_repositories: dict[str, Any]
) -> dict[str, Any]:
    """Seed the storage with the files HACS left behind."""
    hass_storage["hacs.repositories"] = _stored(hacs_repositories)
    hass_storage["hacs.hacs"] = _stored(HACS_COMMON)
    hass_storage["hacs.critical"] = _stored(HACS_CRITICAL)
    return hass_storage


async def test_load(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test loading a store."""
    hass_storage["marketplace.test"] = _stored({"test": "test"})

    assert await async_load_from_storage(hass, "test") == {"test": "test"}


async def test_load_missing(hass: HomeAssistant) -> None:
    """Test loading a store without a file of its own."""
    assert await async_load_from_storage(hass, "test") == {}


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        pytest.param(_stored({"test": "test"}), {"test": "test"}, id="content"),
        pytest.param({}, None, id="empty_file"),
        pytest.param(
            {"version": "0", "data": {"test": "test"}}, None, id="version_mismatch"
        ),
    ],
)
def test_synchronous_load(
    hass: HomeAssistant,
    stored: dict[str, Any],
    expected: dict[str, Any] | None,
) -> None:
    """Test the synchronous load used to read a store off the loop."""
    store = get_storage_for_key(hass, "test")

    with patch(
        "homeassistant.components.marketplace.utils.storage.json_util.load_json",
        return_value=stored,
    ):
        assert store.load() == expected


def test_synchronous_load_unreadable(hass: HomeAssistant) -> None:
    """Test an unreadable store raises."""
    store = get_storage_for_key(hass, "test")

    with (
        patch(
            "homeassistant.components.marketplace.utils.storage.json_util.load_json",
            side_effect=HomeAssistantError("Not valid JSON"),
        ),
        pytest.raises(StoreError),
    ):
        store.load()


async def test_remove(hass: HomeAssistant) -> None:
    """Test only the per repository stores can be removed."""
    with patch(
        "homeassistant.components.marketplace.utils.storage.StoreStorage.async_remove",
        return_value=AsyncMock(),
    ) as async_remove_mock:
        await async_remove_storage(hass, "test")
        assert not async_remove_mock.called

        await async_remove_storage(hass, "test/test")
        assert async_remove_mock.called


async def test_remove_refuses_a_key_outside_the_storage(hass: HomeAssistant) -> None:
    """Test that a repository id can not point the removal out of the storage."""
    with (
        patch(
            "homeassistant.components.marketplace.utils.storage.StoreStorage.async_remove",
            return_value=AsyncMock(),
        ) as async_remove_mock,
        pytest.raises(StoreError, match="is not inside"),
    ):
        await async_remove_storage(hass, "hacs/../../secrets.yaml")

    assert not async_remove_mock.called


async def test_save_skips_unchanged_content(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test saving the same content again does not write."""
    hass_storage["marketplace.test"] = _stored({"test": "test"})

    with patch(
        "homeassistant.components.marketplace.utils.storage.StoreStorage.async_save",
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

    assert hacs_storage["marketplace.repositories"]["data"] == hacs_repositories
    assert hacs_storage["marketplace.common"]["data"] == HACS_COMMON
    assert hacs_storage["marketplace.critical"]["data"] == HACS_CRITICAL

    store = get_store(hass)
    assert {repo.data.full_name for repo in store.repositories.list_downloaded} == {
        REPOSITORY_INTEGRATION,
        REPOSITORY_PLUGIN,
    }
    assert store.common.archived_repositories == {"hacs-test-org/archived"}
    assert store.common.ignored_repositories == {"hacs-test-org/ignored"}
    assert store.common.renamed_repositories == {
        "hacs-test-org/old": "hacs-test-org/new"
    }


async def test_hacs_data_is_left_alone(
    hass: HomeAssistant,
    hacs_storage: dict[str, Any],
    hacs_repositories: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the HACS files stay untouched, they are what a user rolls back to."""
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hacs_storage["hacs.repositories"] == _stored(hacs_repositories)
    assert hacs_storage["hacs.hacs"] == _stored(HACS_COMMON)
    assert hacs_storage["hacs.critical"] == _stored(HACS_CRITICAL)


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

    assert not get_store(hass).repositories.list_downloaded
    assert not get_store(hass).common.archived_repositories


@pytest.mark.usefixtures("hass_storage")
async def test_fresh_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an installation without any stored data at all."""
    await setup_integration(hass, mock_config_entry)

    store = get_store(hass)
    assert store.status.new is True
    assert not store.repositories.list_downloaded


async def test_legacy_hacs_data_fallback(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the data file written by older HACS releases is still read."""
    hass_storage["hacs.data"] = _stored(
        {
            "repositories": {
                "integration": [
                    {
                        "id": "1296269",
                        "full_name": REPOSITORY_INTEGRATION,
                        "installed": True,
                        "version_installed": "1.0.0",
                    }
                ]
            }
        }
    )

    await setup_integration(hass, mock_config_entry)

    store = get_store(hass)
    assert {repo.data.full_name for repo in store.repositories.list_downloaded} == {
        REPOSITORY_INTEGRATION
    }

    # The old file is read, never adopted under one of our own keys
    assert "marketplace.data" not in hass_storage

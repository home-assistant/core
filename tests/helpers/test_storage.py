"""Tests for the storage helper."""
import asyncio
from datetime import timedelta
import json
import os
from typing import Any, NamedTuple
from unittest.mock import Mock, patch

import py
import pytest

from homeassistant.const import (
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir, storage
from homeassistant.util import dt as dt_util
from homeassistant.util.color import RGBColor

from tests.common import async_fire_time_changed, async_test_home_assistant

MOCK_VERSION = 1
MOCK_VERSION_2 = 2
MOCK_MINOR_VERSION_1 = 1
MOCK_MINOR_VERSION_2 = 2
MOCK_KEY = "storage-test"
MOCK_DATA = {"hello": "world"}
MOCK_DATA2 = {"goodbye": "cruel world"}


@pytest.fixture
def store(hass):
    """Fixture of a store that prevents writing on Home Assistant stop."""
    return storage.Store(hass, MOCK_VERSION, MOCK_KEY)


@pytest.fixture
def store_v_1_1(hass):
    """Fixture of a store that prevents writing on Home Assistant stop."""
    return storage.Store(
        hass, MOCK_VERSION, MOCK_KEY, minor_version=MOCK_MINOR_VERSION_1
    )


@pytest.fixture
def store_v_1_2(hass):
    """Fixture of a store that prevents writing on Home Assistant stop."""
    return storage.Store(
        hass, MOCK_VERSION, MOCK_KEY, minor_version=MOCK_MINOR_VERSION_2
    )


@pytest.fixture
def store_v_2_1(hass):
    """Fixture of a store that prevents writing on Home Assistant stop."""
    return storage.Store(
        hass, MOCK_VERSION_2, MOCK_KEY, minor_version=MOCK_MINOR_VERSION_1
    )


@pytest.fixture
def read_only_store(hass):
    """Fixture of a read only store."""
    return storage.Store(hass, MOCK_VERSION, MOCK_KEY, read_only=True)


async def test_loading(hass: HomeAssistant, store) -> None:
    """Test we can save and load data."""
    await store.async_save(MOCK_DATA)
    data = await store.async_load()
    assert data == MOCK_DATA


async def test_custom_encoder(hass: HomeAssistant) -> None:
    """Test we can save and load data."""

    class JSONEncoder(json.JSONEncoder):
        """Mock JSON encoder."""

        def default(self, o):
            """Mock JSON encode method."""
            return "9"

    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY, encoder=JSONEncoder)
    with pytest.raises(TypeError):
        await store.async_save(Mock())
    await store.async_save(object())
    data = await store.async_load()
    assert data == "9"


async def test_loading_non_existing(hass: HomeAssistant, store) -> None:
    """Test we can save and load data."""
    with patch("homeassistant.util.json.open", side_effect=FileNotFoundError):
        data = await store.async_load()
    assert data is None


async def test_loading_parallel(
    hass: HomeAssistant,
    store,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we can save and load data."""
    hass_storage[store.key] = {"version": MOCK_VERSION, "data": MOCK_DATA}

    results = await asyncio.gather(store.async_load(), store.async_load())

    assert results[0] == MOCK_DATA
    assert results[0] is results[1]
    assert caplog.text.count(f"Loading data for {store.key}")


async def test_saving_with_delay(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test saving data after a delay."""
    store.async_delay_save(lambda: MOCK_DATA, 1)
    assert store.key not in hass_storage

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": MOCK_DATA,
    }


async def test_saving_on_final_write(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test delayed saves trigger when we quit Home Assistant."""
    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY)
    store.async_delay_save(lambda: MOCK_DATA, 5)
    assert store.key not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    hass.set_state(CoreState.stopping)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert store.key not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": MOCK_DATA,
    }


async def test_not_delayed_saving_while_stopping(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test delayed saves don't write after the stop event has fired."""
    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    hass.set_state(CoreState.stopping)

    store.async_delay_save(lambda: MOCK_DATA, 1)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert store.key not in hass_storage


async def test_not_delayed_saving_after_stopping(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test delayed saves don't write after stop if issued before stopping Home Assistant."""
    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY)
    store.async_delay_save(lambda: MOCK_DATA, 10)
    assert store.key not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    hass.set_state(CoreState.stopping)
    await hass.async_block_till_done()
    assert store.key not in hass_storage

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
    await hass.async_block_till_done()
    assert store.key not in hass_storage


async def test_not_saving_while_stopping(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test saves don't write when stopping Home Assistant."""
    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY)
    hass.set_state(CoreState.stopping)
    await store.async_save(MOCK_DATA)
    assert store.key not in hass_storage


async def test_loading_while_delay(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test we load new data even if not written yet."""
    await store.async_save({"delay": "no"})
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": {"delay": "no"},
    }

    store.async_delay_save(lambda: {"delay": "yes"}, 1)
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": {"delay": "no"},
    }

    data = await store.async_load()
    assert data == {"delay": "yes"}


async def test_writing_while_writing_delay(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test a write while a write with delay is active."""
    store.async_delay_save(lambda: {"delay": "yes"}, 1)
    assert store.key not in hass_storage
    await store.async_save({"delay": "no"})
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": {"delay": "no"},
    }

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": {"delay": "no"},
    }

    data = await store.async_load()
    assert data == {"delay": "no"}


async def test_multiple_delay_save_calls(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test a write while a write with changing delays."""
    store.async_delay_save(lambda: {"delay": "yes"}, 1)
    store.async_delay_save(lambda: {"delay": "yes"}, 2)
    store.async_delay_save(lambda: {"delay": "yes"}, 3)

    assert store.key not in hass_storage
    await store.async_save({"delay": "no"})
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": {"delay": "no"},
    }

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": {"delay": "no"},
    }

    data = await store.async_load()
    assert data == {"delay": "no"}


async def test_multiple_save_calls(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test multiple write tasks."""

    assert store.key not in hass_storage

    tasks = [store.async_save({"savecount": savecount}) for savecount in range(6)]
    await asyncio.gather(*tasks)
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": {"savecount": 5},
    }

    data = await store.async_load()
    assert data == {"savecount": 5}


async def test_migrator_no_existing_config(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test migrator with no existing config."""
    with patch("os.path.isfile", return_value=False), patch.object(
        store, "async_load", return_value={"cur": "config"}
    ):
        data = await storage.async_migrator(hass, "old-path", store)

    assert data == {"cur": "config"}
    assert store.key not in hass_storage


async def test_migrator_existing_config(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test migrating existing config."""
    with patch("os.path.isfile", return_value=True), patch("os.remove") as mock_remove:
        data = await storage.async_migrator(
            hass, "old-path", store, old_conf_load_func=lambda _: {"old": "config"}
        )

    assert len(mock_remove.mock_calls) == 1
    assert data == {"old": "config"}
    assert hass_storage[store.key] == {
        "key": MOCK_KEY,
        "version": MOCK_VERSION,
        "minor_version": 1,
        "data": data,
    }


async def test_migrator_transforming_config(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test migrating config to new format."""

    async def old_conf_migrate_func(old_config):
        """Migrate old config to new format."""
        return {"new": old_config["old"]}

    with patch("os.path.isfile", return_value=True), patch("os.remove") as mock_remove:
        data = await storage.async_migrator(
            hass,
            "old-path",
            store,
            old_conf_migrate_func=old_conf_migrate_func,
            old_conf_load_func=lambda _: {"old": "config"},
        )

    assert len(mock_remove.mock_calls) == 1
    assert data == {"new": "config"}
    assert hass_storage[store.key] == {
        "key": MOCK_KEY,
        "version": MOCK_VERSION,
        "minor_version": 1,
        "data": data,
    }


async def test_minor_version_default(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test minor version default."""

    await store.async_save(MOCK_DATA)
    assert hass_storage[store.key]["minor_version"] == 1


async def test_minor_version(
    hass: HomeAssistant, store_v_1_2, hass_storage: dict[str, Any]
) -> None:
    """Test minor version."""

    await store_v_1_2.async_save(MOCK_DATA)
    assert hass_storage[store_v_1_2.key]["minor_version"] == MOCK_MINOR_VERSION_2


async def test_migrate_major_not_implemented_raises(
    hass: HomeAssistant, store, store_v_2_1
) -> None:
    """Test migrating between major versions fails if not implemented."""

    await store_v_2_1.async_save(MOCK_DATA)
    with pytest.raises(NotImplementedError):
        await store.async_load()


async def test_migrate_minor_not_implemented(
    hass: HomeAssistant, hass_storage: dict[str, Any], store_v_1_1, store_v_1_2
) -> None:
    """Test migrating between minor versions does not fail if not implemented."""

    assert store_v_1_1.key == store_v_1_2.key

    await store_v_1_1.async_save(MOCK_DATA)
    assert hass_storage[store_v_1_1.key] == {
        "key": MOCK_KEY,
        "version": MOCK_VERSION,
        "minor_version": MOCK_MINOR_VERSION_1,
        "data": MOCK_DATA,
    }
    data = await store_v_1_2.async_load()
    assert hass_storage[store_v_1_1.key]["data"] == data

    await store_v_1_2.async_save(MOCK_DATA)
    assert hass_storage[store_v_1_2.key] == {
        "key": MOCK_KEY,
        "version": MOCK_VERSION,
        "minor_version": MOCK_MINOR_VERSION_2,
        "data": MOCK_DATA,
    }


async def test_migration(
    hass: HomeAssistant, hass_storage: dict[str, Any], store_v_1_2
) -> None:
    """Test migration."""
    calls = 0

    class CustomStore(storage.Store):
        async def _async_migrate_func(
            self, old_major_version, old_minor_version, old_data: dict
        ):
            nonlocal calls
            calls += 1
            assert old_major_version == store_v_1_2.version
            assert old_minor_version == store_v_1_2.minor_version
            return old_data

    await store_v_1_2.async_save(MOCK_DATA)
    assert hass_storage[store_v_1_2.key] == {
        "key": MOCK_KEY,
        "version": MOCK_VERSION,
        "minor_version": MOCK_MINOR_VERSION_2,
        "data": MOCK_DATA,
    }
    assert calls == 0

    custom_store = CustomStore(hass, 2, store_v_1_2.key, minor_version=1)
    data = await custom_store.async_load()
    assert calls == 1
    assert hass_storage[store_v_1_2.key]["data"] == data

    # Assert the migrated data has been saved
    assert hass_storage[custom_store.key] == {
        "key": MOCK_KEY,
        "version": 2,
        "minor_version": 1,
        "data": MOCK_DATA,
    }


async def test_legacy_migration(
    hass: HomeAssistant, hass_storage: dict[str, Any], store_v_1_2
) -> None:
    """Test legacy migration method signature."""
    calls = 0

    class LegacyStore(storage.Store):
        async def _async_migrate_func(self, old_version, old_data: dict):
            nonlocal calls
            calls += 1
            assert old_version == store_v_1_2.version
            return old_data

    await store_v_1_2.async_save(MOCK_DATA)
    assert hass_storage[store_v_1_2.key] == {
        "key": MOCK_KEY,
        "version": MOCK_VERSION,
        "minor_version": MOCK_MINOR_VERSION_2,
        "data": MOCK_DATA,
    }
    assert calls == 0

    legacy_store = LegacyStore(hass, 2, store_v_1_2.key, minor_version=1)
    data = await legacy_store.async_load()
    assert calls == 1
    assert hass_storage[store_v_1_2.key]["data"] == data

    # Assert the migrated data has been saved
    assert hass_storage[legacy_store.key] == {
        "key": MOCK_KEY,
        "version": 2,
        "minor_version": 1,
        "data": MOCK_DATA,
    }


async def test_changing_delayed_written_data(
    hass: HomeAssistant, store, hass_storage: dict[str, Any]
) -> None:
    """Test changing data that is written with delay."""
    data_to_store = {"hello": "world"}
    store.async_delay_save(lambda: data_to_store, 1)
    assert store.key not in hass_storage

    loaded_data = await store.async_load()
    assert loaded_data == data_to_store
    assert loaded_data is not data_to_store

    loaded_data["hello"] = "earth"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass_storage[store.key] == {
        "version": MOCK_VERSION,
        "minor_version": 1,
        "key": MOCK_KEY,
        "data": {"hello": "world"},
    }


async def test_saving_load_round_trip(tmpdir: py.path.local) -> None:
    """Test saving and loading round trip."""
    loop = asyncio.get_running_loop()
    hass = await async_test_home_assistant(loop)

    hass.config.config_dir = await hass.async_add_executor_job(
        tmpdir.mkdir, "temp_storage"
    )

    class NamedTupleSubclass(NamedTuple):
        """A NamedTuple subclass."""

        name: str

    nts = NamedTupleSubclass("a")

    data = {
        "named_tuple_subclass": nts,
        "rgb_color": RGBColor(255, 255, 0),
        "set": {1, 2, 3},
        "list": [1, 2, 3],
        "tuple": (1, 2, 3),
        "dict_with_int": {1: 1, 2: 2},
        "dict_with_named_tuple": {1: nts, 2: nts},
    }

    store = storage.Store(
        hass, MOCK_VERSION_2, MOCK_KEY, minor_version=MOCK_MINOR_VERSION_1
    )
    await store.async_save(data)
    load = await store.async_load()
    assert load == {
        "dict_with_int": {"1": 1, "2": 2},
        "dict_with_named_tuple": {"1": ["a"], "2": ["a"]},
        "list": [1, 2, 3],
        "named_tuple_subclass": ["a"],
        "rgb_color": [255, 255, 0],
        "set": [1, 2, 3],
        "tuple": [1, 2, 3],
    }

    await hass.async_stop(force=True)


async def test_loading_corrupt_core_file(
    tmpdir: py.path.local, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we handle unrecoverable corruption in a core file."""
    loop = asyncio.get_running_loop()
    hass = await async_test_home_assistant(loop)

    tmp_storage = await hass.async_add_executor_job(tmpdir.mkdir, "temp_storage")
    hass.config.config_dir = tmp_storage

    storage_key = "core.anything"
    store = storage.Store(
        hass, MOCK_VERSION_2, storage_key, minor_version=MOCK_MINOR_VERSION_1
    )
    await store.async_save({"hello": "world"})
    storage_path = os.path.join(tmp_storage, ".storage")
    store_file = os.path.join(storage_path, store.key)

    data = await store.async_load()
    assert data == {"hello": "world"}

    def _corrupt_store():
        with open(store_file, "w") as f:
            f.write("corrupt")

    await hass.async_add_executor_job(_corrupt_store)

    data = await store.async_load()
    assert data is None
    assert "Unrecoverable error decoding storage" in caplog.text

    issue_registry = ir.async_get(hass)
    found_issue = None
    issue_entry = None
    for (domain, issue), entry in issue_registry.issues.items():
        if domain == HOMEASSISTANT_DOMAIN and issue.startswith(
            f"storage_corruption_{storage_key}_"
        ):
            found_issue = issue
            issue_entry = entry
            break

    assert found_issue is not None
    assert issue_entry is not None
    assert issue_entry.is_fixable is True
    assert issue_entry.translation_placeholders["storage_key"] == storage_key
    assert issue_entry.issue_domain == HOMEASSISTANT_DOMAIN
    assert (
        issue_entry.translation_placeholders["error"]
        == "unexpected character: line 1 column 1 (char 0)"
    )

    files = await hass.async_add_executor_job(
        os.listdir, os.path.join(tmp_storage, ".storage")
    )
    assert ".corrupt" in files[0]

    await hass.async_stop(force=True)


async def test_loading_corrupt_file_known_domain(
    tmpdir: py.path.local, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we handle unrecoverable corruption for a known domain."""
    loop = asyncio.get_running_loop()
    hass = await async_test_home_assistant(loop)
    hass.config.components.add("testdomain")
    storage_key = "testdomain.testkey"

    tmp_storage = await hass.async_add_executor_job(tmpdir.mkdir, "temp_storage")
    hass.config.config_dir = tmp_storage

    store = storage.Store(
        hass, MOCK_VERSION_2, storage_key, minor_version=MOCK_MINOR_VERSION_1
    )
    await store.async_save({"hello": "world"})
    storage_path = os.path.join(tmp_storage, ".storage")
    store_file = os.path.join(storage_path, store.key)

    data = await store.async_load()
    assert data == {"hello": "world"}

    def _corrupt_store():
        with open(store_file, "w") as f:
            f.write('{"valid":"json"}..with..corrupt')

    await hass.async_add_executor_job(_corrupt_store)

    data = await store.async_load()
    assert data is None
    assert "Unrecoverable error decoding storage" in caplog.text

    issue_registry = ir.async_get(hass)
    found_issue = None
    issue_entry = None
    for (domain, issue), entry in issue_registry.issues.items():
        if domain == HOMEASSISTANT_DOMAIN and issue.startswith(
            f"storage_corruption_{storage_key}_"
        ):
            found_issue = issue
            issue_entry = entry
            break

    assert found_issue is not None
    assert issue_entry is not None
    assert issue_entry.is_fixable is True
    assert issue_entry.translation_placeholders["storage_key"] == storage_key
    assert issue_entry.issue_domain == "testdomain"
    assert (
        issue_entry.translation_placeholders["error"]
        == "unexpected content after document: line 1 column 17 (char 16)"
    )

    files = await hass.async_add_executor_job(
        os.listdir, os.path.join(tmp_storage, ".storage")
    )
    assert ".corrupt" in files[0]

    await hass.async_stop(force=True)


async def test_os_error_is_fatal(tmpdir: py.path.local) -> None:
    """Test OSError during load is fatal."""
    loop = asyncio.get_running_loop()
    hass = await async_test_home_assistant(loop)

    tmp_storage = await hass.async_add_executor_job(tmpdir.mkdir, "temp_storage")
    hass.config.config_dir = tmp_storage

    store = storage.Store(
        hass, MOCK_VERSION_2, MOCK_KEY, minor_version=MOCK_MINOR_VERSION_1
    )
    await store.async_save({"hello": "world"})

    with pytest.raises(OSError), patch(
        "homeassistant.helpers.storage.json_util.load_json", side_effect=OSError
    ):
        await store.async_load()

    base_os_error = OSError()
    base_os_error.errno = 30
    home_assistant_error = HomeAssistantError()
    home_assistant_error.__cause__ = base_os_error

    with pytest.raises(HomeAssistantError), patch(
        "homeassistant.helpers.storage.json_util.load_json",
        side_effect=home_assistant_error,
    ):
        await store.async_load()

    await hass.async_stop(force=True)


async def test_read_only_store(
    hass: HomeAssistant, read_only_store, hass_storage: dict[str, Any]
) -> None:
    """Test store opened in read only mode does not save."""
    read_only_store.async_delay_save(lambda: MOCK_DATA, 1)
    assert read_only_store.key not in hass_storage

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert read_only_store.key not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    hass.set_state(CoreState.stopping)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert read_only_store.key not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()
    assert read_only_store.key not in hass_storage

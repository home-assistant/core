"""Tests for the storage helper."""
import asyncio
from datetime import timedelta
import json
from unittest.mock import patch, Mock

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import storage
from homeassistant.util import dt

from tests.common import async_fire_time_changed, mock_coro


MOCK_VERSION = 1
MOCK_KEY = 'storage-test'
MOCK_DATA = {'hello': 'world'}
MOCK_DATA2 = {'goodbye': 'cruel world'}


@pytest.fixture
def store(hass):
    """Fixture of a store that prevents writing on HASS stop."""
    yield storage.Store(hass, MOCK_VERSION, MOCK_KEY)


async def test_loading(hass, store):
    """Test we can save and load data."""
    await store.async_save(MOCK_DATA)
    data = await store.async_load()
    assert data == MOCK_DATA


async def test_custom_encoder(hass):
    """Test we can save and load data."""
    class JSONEncoder(json.JSONEncoder):
        """Mock JSON encoder."""

        def default(self, o):
            """Mock JSON encode method."""
            return "9"

    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY, encoder=JSONEncoder)
    await store.async_save(Mock())
    data = await store.async_load()
    assert data == "9"


async def test_loading_non_existing(hass, store):
    """Test we can save and load data."""
    with patch('homeassistant.util.json.open', side_effect=FileNotFoundError):
        data = await store.async_load()
    assert data is None


async def test_loading_parallel(hass, store, hass_storage, caplog):
    """Test we can save and load data."""
    hass_storage[store.key] = {
        'version': MOCK_VERSION,
        'data': MOCK_DATA,
    }

    results = await asyncio.gather(
        store.async_load(),
        store.async_load()
    )

    assert results[0] is MOCK_DATA
    assert results[1] is MOCK_DATA
    assert caplog.text.count('Loading data for {}'.format(store.key))


async def test_saving_with_delay(hass, store, hass_storage):
    """Test saving data after a delay."""
    store.async_delay_save(lambda: MOCK_DATA, 1)
    assert store.key not in hass_storage

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass_storage[store.key] == {
        'version': MOCK_VERSION,
        'key': MOCK_KEY,
        'data': MOCK_DATA,
    }


async def test_saving_on_stop(hass, hass_storage):
    """Test delayed saves trigger when we quit Home Assistant."""
    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY)
    store.async_delay_save(lambda: MOCK_DATA, 1)
    assert store.key not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert hass_storage[store.key] == {
        'version': MOCK_VERSION,
        'key': MOCK_KEY,
        'data': MOCK_DATA,
    }


async def test_loading_while_delay(hass, store, hass_storage):
    """Test we load new data even if not written yet."""
    await store.async_save({'delay': 'no'})
    assert hass_storage[store.key] == {
        'version': MOCK_VERSION,
        'key': MOCK_KEY,
        'data': {'delay': 'no'},
    }

    store.async_delay_save(lambda: {'delay': 'yes'}, 1)
    assert hass_storage[store.key] == {
        'version': MOCK_VERSION,
        'key': MOCK_KEY,
        'data': {'delay': 'no'},
    }

    data = await store.async_load()
    assert data == {'delay': 'yes'}


async def test_writing_while_writing_delay(hass, store, hass_storage):
    """Test a write while a write with delay is active."""
    store.async_delay_save(lambda: {'delay': 'yes'}, 1)
    assert store.key not in hass_storage
    await store.async_save({'delay': 'no'})
    assert hass_storage[store.key] == {
        'version': MOCK_VERSION,
        'key': MOCK_KEY,
        'data': {'delay': 'no'},
    }

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass_storage[store.key] == {
        'version': MOCK_VERSION,
        'key': MOCK_KEY,
        'data': {'delay': 'no'},
    }

    data = await store.async_load()
    assert data == {'delay': 'no'}


async def test_migrator_no_existing_config(hass, store, hass_storage):
    """Test migrator with no existing config."""
    with patch('os.path.isfile', return_value=False), \
        patch.object(store, 'async_load',
                     return_value=mock_coro({'cur': 'config'})):
        data = await storage.async_migrator(
            hass, 'old-path', store)

    assert data == {'cur': 'config'}
    assert store.key not in hass_storage


async def test_migrator_existing_config(hass, store, hass_storage):
    """Test migrating existing config."""
    with patch('os.path.isfile', return_value=True), \
            patch('os.remove') as mock_remove:
        data = await storage.async_migrator(
            hass, 'old-path', store,
            old_conf_load_func=lambda _: {'old': 'config'})

    assert len(mock_remove.mock_calls) == 1
    assert data == {'old': 'config'}
    assert hass_storage[store.key] == {
        'key': MOCK_KEY,
        'version': MOCK_VERSION,
        'data': data,
    }


async def test_migrator_transforming_config(hass, store, hass_storage):
    """Test migrating config to new format."""
    async def old_conf_migrate_func(old_config):
        """Migrate old config to new format."""
        return {'new': old_config['old']}

    with patch('os.path.isfile', return_value=True), \
            patch('os.remove') as mock_remove:
        data = await storage.async_migrator(
            hass, 'old-path', store,
            old_conf_migrate_func=old_conf_migrate_func,
            old_conf_load_func=lambda _: {'old': 'config'})

    assert len(mock_remove.mock_calls) == 1
    assert data == {'new': 'config'}
    assert hass_storage[store.key] == {
        'key': MOCK_KEY,
        'version': MOCK_VERSION,
        'data': data,
    }

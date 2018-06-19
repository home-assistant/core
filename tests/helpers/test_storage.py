"""Tests for the storage helper."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import storage
from homeassistant.util import dt

from tests.common import async_fire_time_changed, mock_coro


MOCK_VERSION = 1
MOCK_KEY = 'storage-test'
MOCK_DATA = {'hello': 'world'}


@pytest.fixture
def mock_save():
    """Fixture to mock JSON save."""
    written = []
    with patch('homeassistant.util.json.save_json',
               side_effect=lambda *args: written.append(args)):
        yield written


@pytest.fixture
def mock_load(mock_save):
    """Fixture to mock JSON read."""
    with patch('homeassistant.util.json.load_json',
               side_effect=lambda *args: mock_save[-1][1]):
        yield


@pytest.fixture
def store(hass):
    """Fixture of a store that prevents writing on HASS stop."""
    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY)
    store._async_ensure_stop_listener = lambda: None
    yield store


async def test_loading(hass, store, mock_save, mock_load):
    """Test we can save and load data."""
    await store.async_save(MOCK_DATA)
    data = await store.async_load()
    assert data == MOCK_DATA


async def test_loading_non_existing(hass, store):
    """Test we can save and load data."""
    with patch('homeassistant.util.json.open', side_effect=FileNotFoundError):
        data = await store.async_load()
    assert data == {}


async def test_saving_with_delay(hass, store, mock_save):
    """Test saving data after a delay."""
    await store.async_save(MOCK_DATA, delay=1)
    assert len(mock_save) == 0

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(mock_save) == 1


async def test_saving_on_stop(hass, mock_save):
    """Test delayed saves trigger when we quit Home Assistant."""
    store = storage.Store(hass, MOCK_VERSION, MOCK_KEY)
    await store.async_save(MOCK_DATA, delay=1)
    assert len(mock_save) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_save) == 1


async def test_loading_while_delay(hass, store, mock_save, mock_load):
    """Test we load new data even if not written yet."""
    await store.async_save({'delay': 'no'})
    assert len(mock_save) == 1

    await store.async_save({'delay': 'yes'}, delay=1)
    assert len(mock_save) == 1

    data = await store.async_load()
    assert data == {'delay': 'yes'}


async def test_writing_while_writing_delay(hass, store, mock_save, mock_load):
    """Test a write while a write with delay is active."""
    await store.async_save({'delay': 'yes'}, delay=1)
    assert len(mock_save) == 0
    await store.async_save({'delay': 'no'})
    assert len(mock_save) == 1

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(mock_save) == 1

    data = await store.async_load()
    assert data == {'delay': 'no'}


async def test_migrator_no_existing_config(hass, store, mock_save):
    """Test migrator with no existing config."""
    with patch('os.path.isfile', return_value=False), \
        patch.object(store, 'async_load',
                     return_value=mock_coro({'cur': 'config'})):
        data = await storage.async_migrator(
            hass, 'old-path', store)

    assert data == {'cur': 'config'}
    assert len(mock_save) == 0


async def test_migrator_existing_config(hass, store, mock_save):
    """Test migrating existing config."""
    with patch('os.path.isfile', return_value=True), \
        patch('os.remove') as mock_remove, \
        patch('homeassistant.util.json.load_json',
              return_value={'old': 'config'}):
        data = await storage.async_migrator(
            hass, 'old-path', store)

    assert len(mock_remove.mock_calls) == 1
    assert data == {'old': 'config'}
    assert len(mock_save) == 1
    assert mock_save[0][1] == {
        'key': MOCK_KEY,
        'version': MOCK_VERSION,
        'data': data,
    }


async def test_migrator_transforming_config(hass, store, mock_save):
    """Test migrating config to new format."""
    async def old_conf_migrate_func(old_config):
        """Migrate old config to new format."""
        return {'new': old_config['old']}

    with patch('os.path.isfile', return_value=True), \
        patch('os.remove') as mock_remove, \
        patch('homeassistant.util.json.load_json',
              return_value={'old': 'config'}):
        data = await storage.async_migrator(
            hass, 'old-path', store,
            old_conf_migrate_func=old_conf_migrate_func)

    assert len(mock_remove.mock_calls) == 1
    assert data == {'new': 'config'}
    assert len(mock_save) == 1
    assert mock_save[0][1] == {
        'key': MOCK_KEY,
        'version': MOCK_VERSION,
        'data': data,
    }

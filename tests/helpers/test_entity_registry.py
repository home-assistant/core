"""Tests for the Entity Registry."""
import asyncio
from unittest.mock import patch

import asynctest
import pytest

from homeassistant.core import valid_entity_id
from homeassistant.helpers import entity_registry

from tests.common import mock_registry, flush_store


YAML__OPEN_PATH = 'homeassistant.util.yaml.open'


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


def test_get_or_create_returns_same_entry(registry):
    """Make sure we do not duplicate entries."""
    entry = registry.async_get_or_create('light', 'hue', '1234')
    entry2 = registry.async_get_or_create('light', 'hue', '1234')

    assert len(registry.entities) == 1
    assert entry is entry2
    assert entry.entity_id == 'light.hue_1234'


def test_get_or_create_suggested_object_id(registry):
    """Test that suggested_object_id works."""
    entry = registry.async_get_or_create(
        'light', 'hue', '1234', suggested_object_id='beer')

    assert entry.entity_id == 'light.beer'


def test_get_or_create_suggested_object_id_conflict_register(registry):
    """Test that we don't generate an entity id that is already registered."""
    entry = registry.async_get_or_create(
        'light', 'hue', '1234', suggested_object_id='beer')
    entry2 = registry.async_get_or_create(
        'light', 'hue', '5678', suggested_object_id='beer')

    assert entry.entity_id == 'light.beer'
    assert entry2.entity_id == 'light.beer_2'


def test_get_or_create_suggested_object_id_conflict_existing(hass, registry):
    """Test that we don't generate an entity id that currently exists."""
    hass.states.async_set('light.hue_1234', 'on')
    entry = registry.async_get_or_create('light', 'hue', '1234')
    assert entry.entity_id == 'light.hue_1234_2'


def test_create_triggers_save(hass, registry):
    """Test that registering entry triggers a save."""
    with patch.object(registry, 'async_schedule_save') as mock_schedule_save:
        registry.async_get_or_create('light', 'hue', '1234')

    assert len(mock_schedule_save.mock_calls) == 1


async def test_loading_saving_data(hass, registry):
    """Test that we load/save data correctly."""
    orig_entry1 = registry.async_get_or_create('light', 'hue', '1234')
    orig_entry2 = registry.async_get_or_create(
        'light', 'hue', '5678', config_entry_id='mock-id')

    assert len(registry.entities) == 2

    # Now load written data in new registry
    registry2 = entity_registry.EntityRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    # Ensure same order
    assert list(registry.entities) == list(registry2.entities)
    new_entry1 = registry.async_get_or_create('light', 'hue', '1234')
    new_entry2 = registry.async_get_or_create('light', 'hue', '5678',
                                              config_entry_id='mock-id')

    assert orig_entry1 == new_entry1
    assert orig_entry2 == new_entry2


def test_generate_entity_considers_registered_entities(registry):
    """Test that we don't create entity id that are already registered."""
    entry = registry.async_get_or_create('light', 'hue', '1234')
    assert entry.entity_id == 'light.hue_1234'
    assert registry.async_generate_entity_id('light', 'hue_1234') == \
        'light.hue_1234_2'


def test_generate_entity_considers_existing_entities(hass, registry):
    """Test that we don't create entity id that currently exists."""
    hass.states.async_set('light.kitchen', 'on')
    assert registry.async_generate_entity_id('light', 'kitchen') == \
        'light.kitchen_2'


def test_is_registered(registry):
    """Test that is_registered works."""
    entry = registry.async_get_or_create('light', 'hue', '1234')
    assert registry.async_is_registered(entry.entity_id)
    assert not registry.async_is_registered('light.non_existing')


async def test_loading_extra_values(hass, hass_storage):
    """Test we load extra data from the registry."""
    hass_storage[entity_registry.STORAGE_KEY] = {
        'version': entity_registry.STORAGE_VERSION,
        'data': {
            'entities': [
                {
                    'entity_id': 'test.named',
                    'platform': 'super_platform',
                    'unique_id': 'with-name',
                    'name': 'registry override',
                }, {
                    'entity_id': 'test.no_name',
                    'platform': 'super_platform',
                    'unique_id': 'without-name',
                }, {
                    'entity_id': 'test.disabled_user',
                    'platform': 'super_platform',
                    'unique_id': 'disabled-user',
                    'disabled_by': 'user',
                }, {
                    'entity_id': 'test.disabled_hass',
                    'platform': 'super_platform',
                    'unique_id': 'disabled-hass',
                    'disabled_by': 'hass',
                }
            ]
        }
    }

    registry = await entity_registry.async_get_registry(hass)

    entry_with_name = registry.async_get_or_create(
        'test', 'super_platform', 'with-name')
    entry_without_name = registry.async_get_or_create(
        'test', 'super_platform', 'without-name')
    assert entry_with_name.name == 'registry override'
    assert entry_without_name.name is None
    assert not entry_with_name.disabled

    entry_disabled_hass = registry.async_get_or_create(
        'test', 'super_platform', 'disabled-hass')
    entry_disabled_user = registry.async_get_or_create(
        'test', 'super_platform', 'disabled-user')
    assert entry_disabled_hass.disabled
    assert entry_disabled_hass.disabled_by == entity_registry.DISABLED_HASS
    assert entry_disabled_user.disabled
    assert entry_disabled_user.disabled_by == entity_registry.DISABLED_USER


def test_async_get_entity_id(registry):
    """Test that entity_id is returned."""
    entry = registry.async_get_or_create('light', 'hue', '1234')
    assert entry.entity_id == 'light.hue_1234'
    assert registry.async_get_entity_id(
        'light', 'hue', '1234') == 'light.hue_1234'
    assert registry.async_get_entity_id('light', 'hue', '123') is None


def test_updating_config_entry_id(registry):
    """Test that we update config entry id in registry."""
    entry = registry.async_get_or_create(
        'light', 'hue', '5678', config_entry_id='mock-id-1')
    entry2 = registry.async_get_or_create(
        'light', 'hue', '5678', config_entry_id='mock-id-2')
    assert entry.entity_id == entry2.entity_id
    assert entry2.config_entry_id == 'mock-id-2'


def test_removing_config_entry_id(registry):
    """Test that we update config entry id in registry."""
    entry = registry.async_get_or_create(
        'light', 'hue', '5678', config_entry_id='mock-id-1')
    assert entry.config_entry_id == 'mock-id-1'
    registry.async_clear_config_entry('mock-id-1')

    entry = registry.entities[entry.entity_id]
    assert entry.config_entry_id is None


async def test_migration(hass):
    """Test migration from old data to new."""
    old_conf = {
        'light.kitchen': {
            'config_entry_id': 'test-config-id',
            'unique_id': 'test-unique',
            'platform': 'test-platform',
            'name': 'Test Name',
            'disabled_by': 'hass',
        }
    }
    with patch('os.path.isfile', return_value=True), patch('os.remove'), \
        patch('homeassistant.helpers.entity_registry.load_yaml',
              return_value=old_conf):
        registry = await entity_registry.async_get_registry(hass)

    assert registry.async_is_registered('light.kitchen')
    entry = registry.async_get_or_create(
        domain='light',
        platform='test-platform',
        unique_id='test-unique',
        config_entry_id='test-config-id',
    )
    assert entry.name == 'Test Name'
    assert entry.disabled_by == 'hass'
    assert entry.config_entry_id == 'test-config-id'


async def test_loading_invalid_entity_id(hass, hass_storage):
    """Test we autofix invalid entity IDs."""
    hass_storage[entity_registry.STORAGE_KEY] = {
        'version': entity_registry.STORAGE_VERSION,
        'data': {
            'entities': [
                {
                    'entity_id': 'test.invalid__middle',
                    'platform': 'super_platform',
                    'unique_id': 'id-invalid-middle',
                    'name': 'registry override',
                }, {
                    'entity_id': 'test.invalid_end_',
                    'platform': 'super_platform',
                    'unique_id': 'id-invalid-end',
                }, {
                    'entity_id': 'test._invalid_start',
                    'platform': 'super_platform',
                    'unique_id': 'id-invalid-start',
                }
            ]
        }
    }

    registry = await entity_registry.async_get_registry(hass)

    entity_invalid_middle = registry.async_get_or_create(
        'test', 'super_platform', 'id-invalid-middle')

    assert valid_entity_id(entity_invalid_middle.entity_id)

    entity_invalid_end = registry.async_get_or_create(
        'test', 'super_platform', 'id-invalid-end')

    assert valid_entity_id(entity_invalid_end.entity_id)

    entity_invalid_start = registry.async_get_or_create(
        'test', 'super_platform', 'id-invalid-start')

    assert valid_entity_id(entity_invalid_start.entity_id)


async def test_loading_race_condition(hass):
    """Test only one storage load called when concurrent loading occurred ."""
    with asynctest.patch(
        'homeassistant.helpers.entity_registry.EntityRegistry.async_load',
    ) as mock_load:
        results = await asyncio.gather(
            entity_registry.async_get_registry(hass),
            entity_registry.async_get_registry(hass),
        )

        mock_load.assert_called_once_with()
        assert results[0] == results[1]

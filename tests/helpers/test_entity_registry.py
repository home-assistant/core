"""Tests for the Entity Registry."""
import asyncio
from unittest.mock import patch, mock_open

import pytest

from homeassistant.helpers import entity_registry

from tests.common import mock_registry


YAML__OPEN_PATH = 'homeassistant.util.yaml.open'


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@asyncio.coroutine
def test_get_or_create_returns_same_entry(registry):
    """Make sure we do not duplicate entries."""
    entry = registry.async_get_or_create('light', 'hue', '1234')
    entry2 = registry.async_get_or_create('light', 'hue', '1234')

    assert len(registry.entities) == 1
    assert entry is entry2
    assert entry.entity_id == 'light.hue_1234'


@asyncio.coroutine
def test_get_or_create_suggested_object_id(registry):
    """Test that suggested_object_id works."""
    entry = registry.async_get_or_create(
        'light', 'hue', '1234', suggested_object_id='beer')

    assert entry.entity_id == 'light.beer'


@asyncio.coroutine
def test_get_or_create_suggested_object_id_conflict_register(registry):
    """Test that we don't generate an entity id that is already registered."""
    entry = registry.async_get_or_create(
        'light', 'hue', '1234', suggested_object_id='beer')
    entry2 = registry.async_get_or_create(
        'light', 'hue', '5678', suggested_object_id='beer')

    assert entry.entity_id == 'light.beer'
    assert entry2.entity_id == 'light.beer_2'


@asyncio.coroutine
def test_get_or_create_suggested_object_id_conflict_existing(hass, registry):
    """Test that we don't generate an entity id that currently exists."""
    hass.states.async_set('light.hue_1234', 'on')
    entry = registry.async_get_or_create('light', 'hue', '1234')
    assert entry.entity_id == 'light.hue_1234_2'


@asyncio.coroutine
def test_create_triggers_save(hass, registry):
    """Test that registering entry triggers a save."""
    with patch.object(hass.loop, 'call_later') as mock_call_later:
        registry.async_get_or_create('light', 'hue', '1234')

    assert len(mock_call_later.mock_calls) == 1


@asyncio.coroutine
def test_save_timer_reset_on_subsequent_save(hass, registry):
    """Test we reset the save timer on a new create."""
    with patch.object(hass.loop, 'call_later') as mock_call_later:
        registry.async_get_or_create('light', 'hue', '1234')

    assert len(mock_call_later.mock_calls) == 1

    with patch.object(hass.loop, 'call_later') as mock_call_later_2:
        registry.async_get_or_create('light', 'hue', '5678')

    assert len(mock_call_later().cancel.mock_calls) == 1
    assert len(mock_call_later_2.mock_calls) == 1


@asyncio.coroutine
def test_loading_saving_data(hass, registry):
    """Test that we load/save data correctly."""
    orig_entry1 = registry.async_get_or_create('light', 'hue', '1234')
    orig_entry2 = registry.async_get_or_create('light', 'hue', '5678')

    assert len(registry.entities) == 2

    with patch(YAML__OPEN_PATH, mock_open(), create=True) as mock_write:
        yield from registry._async_save()

    # Mock open calls are: open file, context enter, write, context leave
    written = mock_write.mock_calls[2][1][0]

    # Now load written data in new registry
    registry2 = entity_registry.EntityRegistry(hass)

    with patch('os.path.isfile', return_value=True), \
            patch(YAML__OPEN_PATH, mock_open(read_data=written), create=True):
        yield from registry2._async_load()

    # Ensure same order
    assert list(registry.entities) == list(registry2.entities)
    new_entry1 = registry.async_get_or_create('light', 'hue', '1234')
    new_entry2 = registry.async_get_or_create('light', 'hue', '5678')

    assert orig_entry1 == new_entry1
    assert orig_entry2 == new_entry2


@asyncio.coroutine
def test_generate_entity_considers_registered_entities(registry):
    """Test that we don't create entity id that are already registered."""
    entry = registry.async_get_or_create('light', 'hue', '1234')
    assert entry.entity_id == 'light.hue_1234'
    assert registry.async_generate_entity_id('light', 'hue_1234') == \
        'light.hue_1234_2'


@asyncio.coroutine
def test_generate_entity_considers_existing_entities(hass, registry):
    """Test that we don't create entity id that currently exists."""
    hass.states.async_set('light.kitchen', 'on')
    assert registry.async_generate_entity_id('light', 'kitchen') == \
        'light.kitchen_2'


@asyncio.coroutine
def test_is_registered(registry):
    """Test that is_registered works."""
    entry = registry.async_get_or_create('light', 'hue', '1234')
    assert registry.async_is_registered(entry.entity_id)
    assert not registry.async_is_registered('light.non_existing')


@asyncio.coroutine
def test_loading_extra_values(hass):
    """Test we load extra data from the registry."""
    written = """
test.named:
  platform: super_platform
  unique_id: with-name
  name: registry override
test.no_name:
  platform: super_platform
  unique_id: without-name
test.disabled_user:
  platform: super_platform
  unique_id: disabled-user
  disabled_by: user
test.disabled_hass:
  platform: super_platform
  unique_id: disabled-hass
  disabled_by: hass
"""

    registry = entity_registry.EntityRegistry(hass)

    with patch('os.path.isfile', return_value=True), \
            patch(YAML__OPEN_PATH, mock_open(read_data=written), create=True):
        yield from registry._async_load()

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


@asyncio.coroutine
def test_async_get_entity_id(registry):
    """Test that entity_id is returned."""
    entry = registry.async_get_or_create('light', 'hue', '1234')
    assert entry.entity_id == 'light.hue_1234'
    assert registry.async_get_entity_id(
        'light', 'hue', '1234') == 'light.hue_1234'
    assert registry.async_get_entity_id('light', 'hue', '123') is None

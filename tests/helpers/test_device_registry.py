"""Tests for the Device Registry."""
import pytest

from homeassistant.helpers import device_registry
from tests.common import mock_device_registry


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


async def test_get_or_create_returns_same_entry(registry):
    """Make sure we do not duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id='1234',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry2 = registry.async_get_or_create(
        config_entry_id='1234',
        connections={('ethernet', '11:22:33:44:55:66:77:88')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry3 = registry.async_get_or_create(
        config_entry_id='1234',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '1234')},
        manufacturer='manufacturer', model='model')

    assert len(registry.devices) == 1
    assert entry.id == entry2.id
    assert entry.id == entry3.id
    assert entry.identifiers == {('bridgeid', '0123')}


async def test_requirement_for_identifier_or_connection(registry):
    """Make sure we do require some descriptor of device."""
    entry = registry.async_get_or_create(
        config_entry_id='1234',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers=set(),
        manufacturer='manufacturer', model='model')
    entry2 = registry.async_get_or_create(
        config_entry_id='1234',
        connections=set(),
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry3 = registry.async_get_or_create(
        config_entry_id='1234',
        connections=set(),
        identifiers=set(),
        manufacturer='manufacturer', model='model')

    assert len(registry.devices) == 2
    assert entry
    assert entry2
    assert entry3 is None


async def test_multiple_config_entries(registry):
    """Make sure we do not get duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id='123',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry2 = registry.async_get_or_create(
        config_entry_id='456',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry3 = registry.async_get_or_create(
        config_entry_id='123',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')

    assert len(registry.devices) == 1
    assert entry.id == entry2.id
    assert entry.id == entry3.id
    assert entry2.config_entries == {'123', '456'}


async def test_loading_from_storage(hass, hass_storage):
    """Test loading stored devices on start."""
    hass_storage[device_registry.STORAGE_KEY] = {
        'version': device_registry.STORAGE_VERSION,
        'data': {
            'devices': [
                {
                    'config_entries': [
                        '1234'
                    ],
                    'connections': [
                        [
                            'Zigbee',
                            '01.23.45.67.89'
                        ]
                    ],
                    'id': 'abcdefghijklm',
                    'identifiers': [
                        [
                            'serial',
                            '12:34:56:78:90:AB:CD:EF'
                        ]
                    ],
                    'manufacturer': 'manufacturer',
                    'model': 'model',
                    'name': 'name',
                    'sw_version': 'version',
                }
            ]
        }
    }

    registry = await device_registry.async_get_registry(hass)

    entry = registry.async_get_or_create(
        config_entry_id='1234',
        connections={('Zigbee', '01.23.45.67.89')},
        identifiers={('serial', '12:34:56:78:90:AB:CD:EF')},
        manufacturer='manufacturer', model='model')
    assert entry.id == 'abcdefghijklm'
    assert isinstance(entry.config_entries, set)


async def test_removing_config_entries(registry):
    """Make sure we do not get duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id='123',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry2 = registry.async_get_or_create(
        config_entry_id='456',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry3 = registry.async_get_or_create(
        config_entry_id='123',
        connections={('ethernet', '34:56:78:90:AB:CD:EF:12')},
        identifiers={('bridgeid', '4567')},
        manufacturer='manufacturer', model='model')

    assert len(registry.devices) == 2
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {'123', '456'}

    registry.async_clear_config_entry('123')
    entry = registry.async_get_device({('bridgeid', '0123')}, set())
    entry3 = registry.async_get_device({('bridgeid', '4567')}, set())

    assert entry.config_entries == {'456'}
    assert entry3.config_entries == set()


async def test_specifying_hub_device_create(registry):
    """Test specifying a hub and updating."""
    hub = registry.async_get_or_create(
        config_entry_id='123',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('hue', '0123')},
        manufacturer='manufacturer', model='hub')

    light = registry.async_get_or_create(
        config_entry_id='456',
        connections=set(),
        identifiers={('hue', '456')},
        manufacturer='manufacturer', model='light',
        via_hub=('hue', '0123'))

    assert light.hub_device_id == hub.id


async def test_specifying_hub_device_update(registry):
    """Test specifying a hub and updating."""
    light = registry.async_get_or_create(
        config_entry_id='456',
        connections=set(),
        identifiers={('hue', '456')},
        manufacturer='manufacturer', model='light',
        via_hub=('hue', '0123'))

    assert light.hub_device_id is None

    hub = registry.async_get_or_create(
        config_entry_id='123',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('hue', '0123')},
        manufacturer='manufacturer', model='hub')

    light = registry.async_get_or_create(
        config_entry_id='456',
        connections=set(),
        identifiers={('hue', '456')},
        manufacturer='manufacturer', model='light',
        via_hub=('hue', '0123'))

    assert light.hub_device_id == hub.id

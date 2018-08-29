"""Tests for the Device Registry."""
import pytest

from collections import OrderedDict

from homeassistant.helpers import device_registry


def mock_registry(hass, mock_entries=None):
    """Mock the Device Registry."""
    registry = device_registry.DeviceRegistry(hass)
    registry.devices = mock_entries or OrderedDict()

    async def _get_reg():
        return registry

    hass.data[device_registry.DATA_REGISTRY] = \
        hass.loop.create_task(_get_reg())
    return registry


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_get_or_create_returns_same_entry(registry):
    """Make sure we do not duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry='1234',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry2 = registry.async_get_or_create(
        config_entry='1234',
        connections={('ethernet', '11:22:33:44:55:66:77:88')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry3 = registry.async_get_or_create(
        config_entry='1234',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '1234')},
        manufacturer='manufacturer', model='model')

    assert len(registry.devices) == 1
    assert entry is entry2
    assert entry is entry3
    assert entry.identifiers == {('bridgeid', '0123')}


async def test_requirement_for_identifier_or_connection(registry):
    """Make sure we do require some descriptor of device."""
    entry = registry.async_get_or_create(
        config_entry='1234',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers=set(),
        manufacturer='manufacturer', model='model')
    entry2 = registry.async_get_or_create(
        config_entry='1234',
        connections=set(),
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry3 = registry.async_get_or_create(
        config_entry='1234',
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
        config_entry='123',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry2 = registry.async_get_or_create(
        config_entry='456',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')
    entry3 = registry.async_get_or_create(
        config_entry='123',
        connections={('ethernet', '12:34:56:78:90:AB:CD:EF')},
        identifiers={('bridgeid', '0123')},
        manufacturer='manufacturer', model='model')

    assert len(registry.devices) == 1
    assert entry is entry2
    assert entry is entry3
    assert entry.config_entries == {'123', '456'}


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
        config_entry='1234',
        connections={('Zigbee', '01.23.45.67.89')},
        identifiers={('serial', '12:34:56:78:90:AB:CD:EF')},
        manufacturer='manufacturer', model='model')
    assert entry.id == 'abcdefghijklm'
    assert isinstance(entry.config_entries, set)

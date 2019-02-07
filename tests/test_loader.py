"""Test to verify that we can load components."""
import asyncio

import pytest

import homeassistant.loader as loader
import homeassistant.components.http as http

from tests.common import MockModule, async_mock_service


def test_set_component(hass):
    """Test if set_component works."""
    comp = object()
    loader.set_component(hass, 'switch.test_set', comp)

    assert loader.get_component(hass, 'switch.test_set') is comp


def test_get_component(hass):
    """Test if get_component works."""
    assert http == loader.get_component(hass, 'http')


def test_component_dependencies(hass):
    """Test if we can get the proper load order of components."""
    loader.set_component(hass, 'mod1', MockModule('mod1'))
    loader.set_component(hass, 'mod2', MockModule('mod2', ['mod1']))
    loader.set_component(hass, 'mod3', MockModule('mod3', ['mod2']))

    assert {'mod1', 'mod2', 'mod3'} == \
        loader.component_dependencies(hass, 'mod3')

    # Create circular dependency
    loader.set_component(hass, 'mod1', MockModule('mod1', ['mod3']))

    with pytest.raises(loader.CircularDependency):
        print(loader.component_dependencies(hass, 'mod3'))

    # Depend on non-existing component
    loader.set_component(hass, 'mod1',
                         MockModule('mod1', ['nonexisting']))

    with pytest.raises(loader.ComponentNotFound):
        print(loader.component_dependencies(hass, 'mod1'))

    # Try to get dependencies for non-existing component
    with pytest.raises(loader.ComponentNotFound):
        print(loader.component_dependencies(hass, 'nonexisting'))


def test_component_loader(hass):
    """Test loading components."""
    components = loader.Components(hass)
    assert components.http.CONFIG_SCHEMA is http.CONFIG_SCHEMA
    assert hass.components.http.CONFIG_SCHEMA is http.CONFIG_SCHEMA


def test_component_loader_non_existing(hass):
    """Test loading components."""
    components = loader.Components(hass)
    with pytest.raises(ImportError):
        components.non_existing


@asyncio.coroutine
def test_component_wrapper(hass):
    """Test component wrapper."""
    calls = async_mock_service(hass, 'persistent_notification', 'create')

    components = loader.Components(hass)
    components.persistent_notification.async_create('message')
    yield from hass.async_block_till_done()

    assert len(calls) == 1


@asyncio.coroutine
def test_helpers_wrapper(hass):
    """Test helpers wrapper."""
    helpers = loader.Helpers(hass)

    result = []

    def discovery_callback(service, discovered):
        """Handle discovery callback."""
        result.append(discovered)

    helpers.discovery.async_listen('service_name', discovery_callback)

    yield from helpers.discovery.async_discover('service_name', 'hello')
    yield from hass.async_block_till_done()

    assert result == ['hello']


async def test_custom_component_name(hass):
    """Test the name attribte of custom components."""
    comp = loader.get_component(hass, 'test_standalone')
    assert comp.__name__ == 'custom_components.test_standalone'
    assert comp.__package__ == 'custom_components'

    comp = loader.get_component(hass, 'test_package')
    assert comp.__name__ == 'custom_components.test_package'
    assert comp.__package__ == 'custom_components.test_package'

    comp = loader.get_component(hass, 'light.test')
    assert comp.__name__ == 'custom_components.light.test'
    assert comp.__package__ == 'custom_components.light'

    # Test custom components is mounted
    from custom_components.test_package import TEST
    assert TEST == 5


async def test_log_warning_custom_component(hass, caplog):
    """Test that we log a warning when loading a custom component."""
    loader.get_component(hass, 'test_standalone')
    assert \
        'You are using a custom component for test_standalone' in caplog.text

    loader.get_component(hass, 'light.test')
    assert 'You are using a custom component for light.test' in caplog.text


async def test_get_platform(hass, caplog):
    """Test get_platform."""
    # Test we prefer embedded over normal platforms."""
    embedded_platform = loader.get_platform(hass, 'switch', 'test_embedded')
    assert embedded_platform.__name__ == \
        'custom_components.test_embedded.switch'

    caplog.clear()

    legacy_platform = loader.get_platform(hass, 'switch', 'test')
    assert legacy_platform.__name__ == 'custom_components.switch.test'
    assert 'Integrations need to be in their own folder.' in caplog.text

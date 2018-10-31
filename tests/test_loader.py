"""Test to verify that we can load components."""
# pylint: disable=protected-access
import asyncio
import unittest

import pytest

import homeassistant.loader as loader
import homeassistant.components.http as http

from tests.common import (
    get_test_home_assistant, MockModule, async_mock_service)


class TestLoader(unittest.TestCase):
    """Test the loader module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up tests."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_set_component(self):
        """Test if set_component works."""
        comp = object()
        loader.set_component(self.hass, 'switch.test_set', comp)

        assert loader.get_component(self.hass, 'switch.test_set') is comp

    def test_get_component(self):
        """Test if get_component works."""
        assert http == loader.get_component(self.hass, 'http')
        assert loader.get_component(self.hass, 'light.hue') is not None

    def test_load_order_component(self):
        """Test if we can get the proper load order of components."""
        loader.set_component(self.hass, 'mod1', MockModule('mod1'))
        loader.set_component(self.hass, 'mod2', MockModule('mod2', ['mod1']))
        loader.set_component(self.hass, 'mod3', MockModule('mod3', ['mod2']))

        assert ['mod1', 'mod2', 'mod3'] == \
            loader.load_order_component(self.hass, 'mod3')

        # Create circular dependency
        loader.set_component(self.hass, 'mod1', MockModule('mod1', ['mod3']))

        assert [] == loader.load_order_component(self.hass, 'mod3')

        # Depend on non-existing component
        loader.set_component(self.hass, 'mod1',
                             MockModule('mod1', ['nonexisting']))

        assert [] == loader.load_order_component(self.hass, 'mod1')

        # Try to get load order for non-existing component
        assert [] == loader.load_order_component(self.hass, 'mod1')


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

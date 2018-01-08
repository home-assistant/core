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
        """Setup tests."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_set_component(self):
        """Test if set_component works."""
        loader.set_component('switch.test_set', http)

        self.assertEqual(http, loader.get_component('switch.test_set'))

    def test_get_component(self):
        """Test if get_component works."""
        self.assertEqual(http, loader.get_component('http'))

        self.assertIsNotNone(loader.get_component('switch.test'))

    def test_load_order_component(self):
        """Test if we can get the proper load order of components."""
        loader.set_component('mod1', MockModule('mod1'))
        loader.set_component('mod2', MockModule('mod2', ['mod1']))
        loader.set_component('mod3', MockModule('mod3', ['mod2']))

        self.assertEqual(
            ['mod1', 'mod2', 'mod3'], loader.load_order_component('mod3'))

        # Create circular dependency
        loader.set_component('mod1', MockModule('mod1', ['mod3']))

        self.assertEqual([], loader.load_order_component('mod3'))

        # Depend on non-existing component
        loader.set_component('mod1', MockModule('mod1', ['nonexisting']))

        self.assertEqual([], loader.load_order_component('mod1'))

        # Try to get load order for non-existing component
        self.assertEqual([], loader.load_order_component('mod1'))


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
    calls = async_mock_service(hass, 'light', 'turn_on')

    components = loader.Components(hass)
    components.light.async_turn_on('light.test')
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

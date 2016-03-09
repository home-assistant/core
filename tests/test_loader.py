"""Test to verify that we can load components."""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import homeassistant.loader as loader
import homeassistant.components.http as http

from tests.common import get_test_home_assistant, MockModule


class TestLoader(unittest.TestCase):
    """Test the loader module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup tests."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
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

    def test_load_order_components(self):
        """Setup loading order of components."""
        loader.set_component('mod1', MockModule('mod1', ['group']))
        loader.set_component('mod2', MockModule('mod2', ['mod1', 'sun']))
        loader.set_component('mod3', MockModule('mod3', ['mod2']))
        loader.set_component('mod4', MockModule('mod4', ['group']))

        self.assertEqual(
            ['group', 'mod4', 'mod1', 'sun', 'mod2', 'mod3'],
            loader.load_order_components(['mod4', 'mod3', 'mod2']))

        loader.set_component('mod1', MockModule('mod1'))
        loader.set_component('mod2', MockModule('mod2', ['group']))

        self.assertEqual(
            ['mod1', 'group', 'mod2'],
            loader.load_order_components(['mod2', 'mod1']))

        # Add a non existing one
        self.assertEqual(
            ['mod1', 'group', 'mod2'],
            loader.load_order_components(['mod2', 'nonexisting', 'mod1']))

        # Depend on a non existing one
        loader.set_component('mod1', MockModule('mod1', ['nonexisting']))

        self.assertEqual(
            ['group', 'mod2'],
            loader.load_order_components(['mod2', 'mod1']))

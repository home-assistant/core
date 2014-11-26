"""
test.test_component_group
~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the group compoments.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
import logging

import homeassistant as ha
import homeassistant.components as comps
import homeassistant.components.group as group


def setUpModule():   # pylint: disable=invalid-name
    """ Setup to ignore group errors. """
    logging.disable(logging.CRITICAL)


class TestComponentsGroup(unittest.TestCase):
    """ Tests homeassistant.components.group module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = ha.HomeAssistant()

        self.hass.states.set('light.Bowl', comps.STATE_ON)
        self.hass.states.set('light.Ceiling', comps.STATE_OFF)
        self.hass.states.set('switch.AC', comps.STATE_OFF)
        group.setup_group(self.hass, 'init_group',
                          ['light.Bowl', 'light.Ceiling'], False)
        group.setup_group(self.hass, 'mixed_group',
                          ['light.Bowl', 'switch.AC'], False)

        self.group_name = group.ENTITY_ID_FORMAT.format('init_group')
        self.mixed_group_name = group.ENTITY_ID_FORMAT.format('mixed_group')

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup_and_monitor_group(self):
        """ Test setup_group method. """

        # Test if group setup in our init mode is ok
        self.assertIn(self.group_name, self.hass.states.entity_ids)

        group_state = self.hass.states.get(self.group_name)
        self.assertEqual(comps.STATE_ON, group_state.state)
        self.assertTrue(group_state.attributes[group.ATTR_AUTO])

        # Turn the Bowl off and see if group turns off
        self.hass.states.set('light.Bowl', comps.STATE_OFF)

        self.hass._pool.block_till_done()

        group_state = self.hass.states.get(self.group_name)
        self.assertEqual(comps.STATE_OFF, group_state.state)

        # Turn the Ceiling on and see if group turns on
        self.hass.states.set('light.Ceiling', comps.STATE_ON)

        self.hass._pool.block_till_done()

        group_state = self.hass.states.get(self.group_name)
        self.assertEqual(comps.STATE_ON, group_state.state)

        # Try to setup a group with mixed groupable states
        self.hass.states.set('device_tracker.Paulus', comps.STATE_HOME)
        self.assertFalse(group.setup_group(
            self.hass, 'person_and_light',
            ['light.Bowl', 'device_tracker.Paulus']))

        # Try to setup a group with a non existing state
        self.assertNotIn('non.existing', self.hass.states.entity_ids)
        self.assertFalse(group.setup_group(
            self.hass, 'light_and_nothing',
            ['light.Bowl', 'non.existing']))

        # Try to setup a group with non groupable states
        self.hass.states.set('cast.living_room', "Plex")
        self.hass.states.set('cast.bedroom', "Netflix")
        self.assertFalse(
            group.setup_group(
                self.hass, 'chromecasts',
                ['cast.living_room', 'cast.bedroom']))

        # Try to setup an empty group
        self.assertFalse(group.setup_group(self.hass, 'nothing', []))

    def test__get_group_type(self):
        """ Test _get_group_type method. """
        self.assertEqual('on_off', group._get_group_type(comps.STATE_ON))
        self.assertEqual('on_off', group._get_group_type(comps.STATE_OFF))
        self.assertEqual('home_not_home',
                         group._get_group_type(comps.STATE_HOME))
        self.assertEqual('home_not_home',
                         group._get_group_type(comps.STATE_NOT_HOME))

        # Unsupported state
        self.assertIsNone(group._get_group_type('unsupported_state'))

    def test_is_on(self):
        """ Test is_on method. """
        self.assertTrue(group.is_on(self.hass, self.group_name))
        self.hass.states.set('light.Bowl', comps.STATE_OFF)
        self.hass._pool.block_till_done()
        self.assertFalse(group.is_on(self.hass, self.group_name))

        # Try on non existing state
        self.assertFalse(group.is_on(self.hass, 'non.existing'))

    def test_expand_entity_ids(self):
        """ Test expand_entity_ids method. """
        self.assertEqual(sorted(['light.Ceiling', 'light.Bowl']),
                         sorted(group.expand_entity_ids(
                             self.hass, [self.group_name])))

        # Make sure that no duplicates are returned
        self.assertEqual(
            sorted(['light.Ceiling', 'light.Bowl']),
            sorted(group.expand_entity_ids(
                self.hass, [self.group_name, 'light.Ceiling'])))

        # Test that non strings are ignored
        self.assertEqual([], group.expand_entity_ids(self.hass, [5, True]))

    def test_get_entity_ids(self):
        """ Test get_entity_ids method. """
        # Get entity IDs from our group
        self.assertEqual(
            sorted(['light.Ceiling', 'light.Bowl']),
            sorted(group.get_entity_ids(self.hass, self.group_name)))

        # Test domain_filter
        self.assertEqual(
            ['switch.AC'],
            group.get_entity_ids(
                self.hass, self.mixed_group_name, domain_filter="switch"))

        # Test with non existing group name
        self.assertEqual([], group.get_entity_ids(self.hass, 'non_existing'))

        # Test with non-group state
        self.assertEqual([], group.get_entity_ids(self.hass, 'switch.AC'))

    def test_setup(self):
        """ Test setup method. """
        self.assertTrue(
            group.setup(
                self.hass,
                {
                    group.DOMAIN: {
                        'second_group': '{},light.Bowl'.format(self.group_name)
                    }
                }))

        group_state = self.hass.states.get(
            group.ENTITY_ID_FORMAT.format('second_group'))

        self.assertEqual(comps.STATE_ON, group_state.state)
        self.assertFalse(group_state.attributes[group.ATTR_AUTO])

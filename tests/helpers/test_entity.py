"""Test the entity helper."""
# pylint: disable=protected-access,too-many-public-methods
import unittest

import homeassistant.helpers.entity as entity
from homeassistant.const import ATTR_HIDDEN

from tests.common import get_test_home_assistant


class TestHelpersEntity(unittest.TestCase):
    """Test homeassistant.helpers.entity module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.entity = entity.Entity()
        self.entity.entity_id = 'test.overwrite_hidden_true'
        self.hass = self.entity.hass = get_test_home_assistant()
        self.entity.update_ha_state()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()
        entity.set_customize({})

    def test_default_hidden_not_in_attributes(self):
        """Test that the default hidden property is set to False."""
        self.assertNotIn(
            ATTR_HIDDEN,
            self.hass.states.get(self.entity.entity_id).attributes)

    def test_overwriting_hidden_property_to_true(self):
        """Test we can overwrite hidden property to True."""
        entity.set_customize({self.entity.entity_id: {ATTR_HIDDEN: True}})
        self.entity.update_ha_state()

        state = self.hass.states.get(self.entity.entity_id)
        self.assertTrue(state.attributes.get(ATTR_HIDDEN))

    def test_split_entity_id(self):
        """Test split_entity_id."""
        self.assertEqual(['domain', 'object_id'],
                         entity.split_entity_id('domain.object_id'))

    def test_generate_entity_id_requires_hass_or_ids(self):
        """Ensure we require at least hass or current ids."""
        fmt = 'test.{}'
        with self.assertRaises(ValueError):
            entity.generate_entity_id(fmt, 'hello world')

    def test_generate_entity_id_given_hass(self):
        """Test generating an entity id given hass object."""
        fmt = 'test.{}'
        self.assertEqual(
            'test.overwrite_hidden_true_2',
            entity.generate_entity_id(fmt, 'overwrite hidden true',
                                      hass=self.hass))

    def test_generate_entity_id_given_keys(self):
        """Test generating an entity id given current ids."""
        fmt = 'test.{}'
        self.assertEqual(
            'test.overwrite_hidden_true_2',
            entity.generate_entity_id(
                fmt, 'overwrite hidden true',
                current_ids=['test.overwrite_hidden_true']))
        self.assertEqual(
            'test.overwrite_hidden_true',
            entity.generate_entity_id(fmt, 'overwrite hidden true',
                                      current_ids=['test.another_entity']))

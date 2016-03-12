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
        entity.Entity.overwrite_attribute(self.entity.entity_id,
                                          [ATTR_HIDDEN], [None])

    def test_default_hidden_not_in_attributes(self):
        """Test that the default hidden property is set to False."""
        self.assertNotIn(
            ATTR_HIDDEN,
            self.hass.states.get(self.entity.entity_id).attributes)

    def test_overwriting_hidden_property_to_true(self):
        """Test we can overwrite hidden property to True."""
        entity.Entity.overwrite_attribute(self.entity.entity_id,
                                          [ATTR_HIDDEN], [True])
        self.entity.update_ha_state()

        state = self.hass.states.get(self.entity.entity_id)
        self.assertTrue(state.attributes.get(ATTR_HIDDEN))

    def test_split_entity_id(self):
        """Test split_entity_id."""
        self.assertEqual(['domain', 'object_id'],
                         entity.split_entity_id('domain.object_id'))

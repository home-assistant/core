"""
tests.test_helper_entity
~~~~~~~~~~~~~~~~~~~~~~~~

Tests the entity helper.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest

import homeassistant as ha
import homeassistant.helpers.entity as entity
from homeassistant.const import ATTR_HIDDEN


class TestHelpersEntity(unittest.TestCase):
    """ Tests homeassistant.helpers.entity module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.entity = entity.Entity()
        self.entity.entity_id = 'test.overwrite_hidden_true'
        self.hass = self.entity.hass = ha.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_default_hidden_not_in_attributes(self):
        """ Test that the default hidden property is set to False. """
        self.entity.update_ha_state()

        self.assertNotIn(
            ATTR_HIDDEN,
            self.hass.states.get(self.entity.entity_id).attributes)

    def test_setting_hidden_to_true(self):
        self.entity.hidden = True
        self.entity.update_ha_state()

        state = self.hass.states.get(self.entity.entity_id)

        self.assertTrue(state.attributes.get(ATTR_HIDDEN))

        self.entity.hidden = False

    def test_overwriting_hidden_property_to_true(self):
        """ Test we can overwrite hidden property to True. """
        entity.Entity.overwrite_hidden(self.entity.entity_id, True)

        self.entity.update_ha_state()

        state = self.hass.states.get(self.entity.entity_id)

        self.assertTrue(state.attributes.get(ATTR_HIDDEN))

        entity.Entity.overwrite_hidden(self.entity.entity_id, None)

    def test_overwriting_hidden_property_to_false(self):
        """ Test we can overwrite hidden property to True. """
        entity.Entity.overwrite_hidden(self.entity.entity_id, False)

        self.entity.hidden = True
        self.entity.update_ha_state()

        self.assertNotIn(
            ATTR_HIDDEN,
            self.hass.states.get(self.entity.entity_id).attributes)

        entity.Entity.overwrite_hidden(self.entity.entity_id, None)

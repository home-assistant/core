"""The tests for the entity_patter_matching helper class."""
import unittest

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.zwave.const import EVENT_NETWORK_READY
from homeassistant.helpers.entity_pattern_matching \
    import EntityPatternMatching as EPM

from tests.common import get_test_home_assistant


class TestEntityPatternMatching(unittest.TestCase):
    """Test the EntityPatterMatching helper class."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everthing that was started."""
        self.hass.stop()

    def test_entity_pattern_matching(self):
        """Test if entity pattern matching works correctly."""
        entity_ids = set()
        update_runs = []
        entity_list = ['light.demo', 'light.b*', 'lig[h]t.demo2',
                       'light?demo3']

        @callback
        def update_entity_ids(new_entity_ids):
            """Method called from EPM to report new entity ids."""
            update_runs.append(new_entity_ids.copy())
            for entity in new_entity_ids:
                self.assertFalse(entity in entity_ids)
            entity_ids.update(new_entity_ids)

        EPM(self.hass, update_entity_ids, entity_list)

        self.assertEqual(1, len(update_runs))
        self.assertEqual(update_runs[0], {'light.demo'})

        self.hass.states.set('light.Bowl', 'on')
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

        self.assertEqual(2, len(update_runs))
        self.assertEqual(update_runs[1], {'light.bowl'})

        self.hass.states.set('light.demo2', 'off')
        self.hass.states.set('light.demo3', 'off')
        self.hass.states.set('cover.living_room', 'open')
        self.hass.bus.fire(EVENT_NETWORK_READY)
        self.hass.block_till_done()

        self.assertEqual(3, len(update_runs))
        self.assertEqual(update_runs[2], {'light.demo2', 'light.demo3'})

"""The tests the Graph component."""

import unittest

from homeassistant.setup import setup_component
from tests.common import init_recorder_component, get_test_home_assistant


class TestGraph(unittest.TestCase):
    """Test the Google component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        self.init_recorder()
        config = {
            'history': {
            },
            'history_graph': {
                'name_1': {
                    'entities': 'test.test',
                }
            }
        }

        self.assertTrue(setup_component(self.hass, 'history_graph', config))
        self.assertEqual(
            dict(self.hass.states.get('history_graph.name_1').attributes),
            {
                'entity_id': ['test.test'],
                'friendly_name': 'name_1',
                'hours_to_show': 24,
                'refresh': 0
            })

    def init_recorder(self):
        """Initialize the recorder."""
        init_recorder_component(self.hass)
        self.hass.start()

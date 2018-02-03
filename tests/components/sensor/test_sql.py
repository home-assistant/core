"""The test for the sql sensor platform."""
import unittest

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestSQLSensor(unittest.TestCase):
    """Test the SQL sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_query(self):
        """Test the SQL sensor."""
        config = {
            'sensor': {
                'platform': 'sql',
                'db_url': 'sqlite://',
                'queries': [{
                    'name': 'count_tables',
                    'query': 'SELECT count(*) value FROM sqlite_master;',
                    'column': 'value',
                }]
            }
        }

        assert setup_component(self.hass, 'sensor', config)

        state = self.hass.states.get('sensor.count_tables')
        self.assertEqual(state.state, '0')

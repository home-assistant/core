"""The tests for local file sensor platform."""
import unittest
from unittest.mock import Mock, patch

# Using third party package because of a bug reading binary data in Python 3.4
# https://bugs.python.org/issue23004
from mock_open import MockOpen

from homeassistant.setup import setup_component
from homeassistant.const import STATE_UNKNOWN

from tests.common import get_test_home_assistant, mock_registry


class TestFileSensor(unittest.TestCase):
    """Test the File sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_registry(self.hass)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('os.path.isfile', Mock(return_value=True))
    @patch('os.access', Mock(return_value=True))
    def test_file_value(self):
        """Test the File sensor."""
        config = {
            'sensor': {
                'platform': 'file',
                'name': 'file1',
                'file_path': 'mock.file1',
            }
        }

        m_open = MockOpen(read_data='43\n45\n21')
        with patch('homeassistant.components.sensor.file.open', m_open,
                   create=True):
            assert setup_component(self.hass, 'sensor', config)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.file1')
        self.assertEqual(state.state, '21')

    @patch('os.path.isfile', Mock(return_value=True))
    @patch('os.access', Mock(return_value=True))
    def test_file_value_template(self):
        """Test the File sensor with JSON entries."""
        config = {
            'sensor': {
                'platform': 'file',
                'name': 'file2',
                'file_path': 'mock.file2',
                'value_template': '{{ value_json.temperature }}',
            }
        }

        data = '{"temperature": 29, "humidity": 31}\n' \
               '{"temperature": 26, "humidity": 36}'

        m_open = MockOpen(read_data=data)
        with patch('homeassistant.components.sensor.file.open', m_open,
                   create=True):
            assert setup_component(self.hass, 'sensor', config)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.file2')
        self.assertEqual(state.state, '26')

    @patch('os.path.isfile', Mock(return_value=True))
    @patch('os.access', Mock(return_value=True))
    def test_file_empty(self):
        """Test the File sensor with an empty file."""
        config = {
            'sensor': {
                'platform': 'file',
                'name': 'file3',
                'file_path': 'mock.file',
            }
        }

        m_open = MockOpen(read_data='')
        with patch('homeassistant.components.sensor.file.open', m_open,
                   create=True):
            assert setup_component(self.hass, 'sensor', config)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.file3')
        self.assertEqual(state.state, STATE_UNKNOWN)

"""The tests for local file sensor platform."""
import json
import unittest
from unittest.mock import Mock, patch

# Using third party package because of a bug reading binary data in Python 3.4
# https://bugs.python.org/issue23004
from mock_open import MockOpen

from homeassistant.setup import setup_component
from homeassistant.const import STATE_UNKNOWN

from tests.common import get_test_home_assistant


def create_file(path, data):
    """Create a sensor file."""
    with open(path, 'w') as test_file:
        test_file.write(data)


class TestFileSensor(unittest.TestCase):
    """Test the File sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

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

        assert setup_component(self.hass, 'sensor', config)

        create_file('mock.file1', '43\n45\n21')

        m_open = MockOpen()
        with patch('homeassistant.components.sensor.file.open', m_open,
                   create=True):
            content = open('mock.file1')
            result = content.readlines()[-1].strip()

        self.assertEqual(result, '21')

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

        assert setup_component(self.hass, 'sensor', config)

        create_file('mock.file2',
                    '{"temperature": 29, "humidity": 31}\n'
                    '{"temperature": 26, "humidity": 36}')

        m_open = MockOpen()
        with patch('homeassistant.components.sensor.file.open', m_open,
                   create=True):
            content = open('mock.file2')
            result = content.readlines()[-1].strip()

        self.assertEqual(result, '{"temperature": 26, "humidity": 36}')

        state = self.hass.states.get('sensor.file2')
        self.assertEqual(state.state, str(json.loads(result)['temperature']))

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

        assert setup_component(self.hass, 'sensor', config)

        create_file('mock.file', '')

        m_open = MockOpen()
        with patch('homeassistant.components.sensor.file.open', m_open,
                   create=True):
            content = open('mock.file')
            result = content.read()

        self.assertEqual(result, '')

        state = self.hass.states.get('sensor.file3')
        self.assertEqual(state.state, STATE_UNKNOWN)

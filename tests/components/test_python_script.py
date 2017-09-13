"""The tests for the Python Script component."""
# pylint: disable=protected-access
import unittest

from homeassistant.core import callback
from homeassistant.bootstrap import setup_component
from homeassistant.components import python_script

from tests.common import get_test_home_assistant


ENTITY_ID = 'python_script.test'


class TestPythonScriptComponent(unittest.TestCase):
    """Test the Script component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.append('group')

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()
        
    def test_datetime(self):
        pass
        
    def test_unpack_sequence(self):
        calls = []
        @callback
        def record_call(service):
            """Add recorded event to set."""
            calls.append(service)

        self.hass.services.register('test', 'python_script', record_call)
        assert setup_component(self.hass, 'python_script', {
            'python_script': {
            },
        })
        source = '''
        
        a,b = (1,2)
        ab_list = [(a,b) for a,b in [(1,2),(3,4)]]
        data['a'] = a
        data['b'] = b
        data['ab_list'] = ab_list
        '''
        data = {}
        python_script.execute(self.hass, 'dummy.py', source, data)
        assert data['a'] == 1
        assert data['b'] == 2
        assert data['ab_list'] == [(1,2),(3,4)]


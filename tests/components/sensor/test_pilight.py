"""The tests for the Pilight sensor platform."""
import unittest
from unittest.mock import patch

from homeassistant.bootstrap import _setup_component
import homeassistant.components.sensor as sensor
from homeassistant.components import pilight

from tests.common import get_test_home_assistant


def fire_pilight_message(hass, protocol, data):
    """Fire the fake pilight message."""
    hass.bus.fire(pilight.EVENT, {
        pilight.ATTR_PROTOCOL: protocol,
        **data
    })


class TestSensorPilight(unittest.TestCase):
    """Test the Pilight sensor."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components = ['pilight']

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_sensor_value_from_code(self):
        """Test the setting of value via pilight."""
        assert _setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'pilight',
                'name': 'test',
                'variable': 'test',
                'payload': {'protocol': 'test-protocol'},
                'unit_of_measurement': 'fav unit'
            }
        })

        # Set value from data with correct payload
        fire_pilight_message(hass=self.hass,
                             protocol='test-protocol',
                             data={'test': 42})
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')
        self.assertEqual('42', state.state)

        # Check if unit is set properly
        self.assertEqual('fav unit',
                         state.attributes.get('unit_of_measurement'))

    def test_disregard_wrong_payload(self):
        """Test omitting setting of value with wrong payload."""

        assert _setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'pilight',
                'name': 'test',
                'variable': 'test',
                'payload': {'uuid': '1-2-3-4',
                            'protocol': 'test-protocol'}
            }
        })

        # Try set value from data with incorrect payload
        fire_pilight_message(hass=self.hass,
                             protocol='test-protocol',
                             data={'test': 'data',
                                   'uuid': '0-0-0-0'})
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')
        self.assertEqual('unknown', state.state)

        # Try set value from data with partially matched payload
        fire_pilight_message(hass=self.hass,
                             protocol='wrong-protocol',
                             data={'test': 'data',
                                   'uuid': '1-2-3-4'})
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')
        self.assertEqual('unknown', state.state)

        # Try set value from data with fully matched payload
        fire_pilight_message(hass=self.hass,
                             protocol='test-protocol',
                             data={'test': 'data',
                                   'uuid': '1-2-3-4',
                                   'other_payload': 3.141})
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test')
        self.assertEqual('data', state.state)

    @unittest.SkipTest
    @patch('homeassistant.components.sensor.pilight._LOGGER')
    def test_variable_missing(self, log_mock):
        """Check if error message when variable missing."""
        self.hass.config.components = ['pilight']
        assert _setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'pilight',
                'name': 'test',
                'variable': 'test',
                'payload': {'protocol': 'test-protocol'}
            }
        })

        # Create code without sensor variable
        fire_pilight_message(hass=self.hass,
                             protocol='test-protocol',
                             data={'uuid': '1-2-3-4',
                                   'other_variable': 3.141})

        # FIXME: The following gives a wrong 0, I do not see why
        # Maybe because of catchlog?
        self.assertEqual(log_mock.error.call_count, 1)

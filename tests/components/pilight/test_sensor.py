"""The tests for the Pilight sensor platform."""
import logging

from homeassistant.setup import setup_component
import homeassistant.components.sensor as sensor
from homeassistant.components import pilight

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_component)

HASS = None


def fire_pilight_message(protocol, data):
    """Fire the fake Pilight message."""
    message = {pilight.CONF_PROTOCOL: protocol}
    message.update(data)
    HASS.bus.fire(pilight.EVENT, message)


# pylint: disable=invalid-name
def setup_function():
    """Initialize a Home Assistant server."""
    global HASS

    HASS = get_test_home_assistant()
    mock_component(HASS, 'pilight')


# pylint: disable=invalid-name
def teardown_function():
    """Stop the Home Assistant server."""
    HASS.stop()


def test_sensor_value_from_code():
    """Test the setting of value via pilight."""
    with assert_setup_component(1):
        setup_component(HASS, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'pilight',
                'name': 'test',
                'variable': 'test',
                'payload': {'protocol': 'test-protocol'},
                'unit_of_measurement': 'fav unit'
            }
        })

        state = HASS.states.get('sensor.test')
        assert state.state == 'unknown'

        unit_of_measurement = state.attributes.get('unit_of_measurement')
        assert unit_of_measurement == 'fav unit'

        # Set value from data with correct payload
        fire_pilight_message(protocol='test-protocol',
                             data={'test': 42})
        HASS.block_till_done()
        state = HASS.states.get('sensor.test')
        assert state.state == '42'


def test_disregard_wrong_payload():
    """Test omitting setting of value with wrong payload."""
    with assert_setup_component(1):
        setup_component(HASS, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'pilight',
                'name': 'test_2',
                'variable': 'test',
                'payload': {
                    'uuid': '1-2-3-4',
                    'protocol': 'test-protocol_2'
                }
            }
        })

        # Try set value from data with incorrect payload
        fire_pilight_message(protocol='test-protocol_2',
                             data={'test': 'data', 'uuid': '0-0-0-0'})
        HASS.block_till_done()
        state = HASS.states.get('sensor.test_2')
        assert state.state == 'unknown'

        # Try set value from data with partially matched payload
        fire_pilight_message(protocol='wrong-protocol',
                             data={'test': 'data', 'uuid': '1-2-3-4'})
        HASS.block_till_done()
        state = HASS.states.get('sensor.test_2')
        assert state.state == 'unknown'

        # Try set value from data with fully matched payload
        fire_pilight_message(protocol='test-protocol_2',
                             data={'test': 'data',
                                   'uuid': '1-2-3-4',
                                   'other_payload': 3.141})
        HASS.block_till_done()
        state = HASS.states.get('sensor.test_2')
        assert state.state == 'data'


def test_variable_missing(caplog):
    """Check if error message when variable missing."""
    caplog.set_level(logging.ERROR)
    with assert_setup_component(1):
        setup_component(HASS, sensor.DOMAIN, {
            sensor.DOMAIN: {
                'platform': 'pilight',
                'name': 'test_3',
                'variable': 'test',
                'payload': {'protocol': 'test-protocol'}
            }
        })

        # Create code without sensor variable
        fire_pilight_message(protocol='test-protocol',
                             data={'uuid': '1-2-3-4', 'other_variable': 3.141})
        HASS.block_till_done()

        logs = caplog.text

        assert 'No variable test in received code' in logs

"""The tests for the litejet component."""
import logging
import unittest
from unittest import mock
from datetime import timedelta

from homeassistant import setup
import homeassistant.util.dt as dt_util
from homeassistant.components import litejet
from tests.common import (fire_time_changed, get_test_home_assistant)
import homeassistant.components.automation as automation

_LOGGER = logging.getLogger(__name__)

ENTITY_SWITCH = 'switch.mock_switch_1'
ENTITY_SWITCH_NUMBER = 1
ENTITY_OTHER_SWITCH = 'switch.mock_switch_2'
ENTITY_OTHER_SWITCH_NUMBER = 2


class TestLiteJetTrigger(unittest.TestCase):
    """Test the litejet component."""

    @mock.patch('pylitejet.LiteJet')
    def setup_method(self, method, mock_pylitejet):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.start()

        self.switch_pressed_callbacks = {}
        self.switch_released_callbacks = {}
        self.calls = []

        def get_switch_name(number):
            return "Mock Switch #"+str(number)

        def on_switch_pressed(number, callback):
            self.switch_pressed_callbacks[number] = callback

        def on_switch_released(number, callback):
            self.switch_released_callbacks[number] = callback

        def record_call(service):
            self.calls.append(service)

        self.mock_lj = mock_pylitejet.return_value
        self.mock_lj.loads.return_value = range(0)
        self.mock_lj.button_switches.return_value = range(1, 3)
        self.mock_lj.all_switches.return_value = range(1, 6)
        self.mock_lj.scenes.return_value = range(0)
        self.mock_lj.get_switch_name.side_effect = get_switch_name
        self.mock_lj.on_switch_pressed.side_effect = on_switch_pressed
        self.mock_lj.on_switch_released.side_effect = on_switch_released

        config = {
            'litejet': {
                'port': '/tmp/this_will_be_mocked'
            }
        }
        assert setup.setup_component(self.hass, litejet.DOMAIN, config)

        self.hass.services.register('test', 'automation', record_call)

        self.hass.block_till_done()

        self.start_time = dt_util.utcnow()
        self.last_delta = timedelta(0)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def simulate_press(self, number):
        """Test to simulate a press."""
        _LOGGER.info('*** simulate press of %d', number)
        callback = self.switch_pressed_callbacks.get(number)
        with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                        return_value=self.start_time + self.last_delta):
            if callback is not None:
                callback()
            self.hass.block_till_done()

    def simulate_release(self, number):
        """Test to simulate releasing."""
        _LOGGER.info('*** simulate release of %d', number)
        callback = self.switch_released_callbacks.get(number)
        with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                        return_value=self.start_time + self.last_delta):
            if callback is not None:
                callback()
            self.hass.block_till_done()

    def simulate_time(self, delta):
        """Test to simulate time."""
        _LOGGER.info(
            '*** simulate time change by %s: %s',
            delta,
            self.start_time + delta)
        self.last_delta = delta
        with mock.patch('homeassistant.helpers.condition.dt_util.utcnow',
                        return_value=self.start_time + delta):
            _LOGGER.info('now=%s', dt_util.utcnow())
            fire_time_changed(self.hass, self.start_time + delta)
            self.hass.block_till_done()
            _LOGGER.info('done with now=%s', dt_util.utcnow())

    def setup_automation(self, trigger):
        """Test setting up the automation."""
        assert setup.setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: [
                {
                    'alias': 'My Test',
                    'trigger': trigger,
                    'action': {
                        'service': 'test.automation'
                    }
                }
            ]
        })
        self.hass.block_till_done()

    def test_simple(self):
        """Test the simplest form of a LiteJet trigger."""
        self.setup_automation({
            'platform': 'litejet',
            'number': ENTITY_OTHER_SWITCH_NUMBER
        })

        self.simulate_press(ENTITY_OTHER_SWITCH_NUMBER)
        self.simulate_release(ENTITY_OTHER_SWITCH_NUMBER)

        assert len(self.calls) == 1

    def test_held_more_than_short(self):
        """Test a too short hold."""
        self.setup_automation({
            'platform': 'litejet',
            'number': ENTITY_OTHER_SWITCH_NUMBER,
            'held_more_than': {
                'milliseconds': '200'
            }
        })

        self.simulate_press(ENTITY_OTHER_SWITCH_NUMBER)
        self.simulate_time(timedelta(seconds=0.1))
        self.simulate_release(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 0

    def test_held_more_than_long(self):
        """Test a hold that is long enough."""
        self.setup_automation({
            'platform': 'litejet',
            'number': ENTITY_OTHER_SWITCH_NUMBER,
            'held_more_than': {
                'milliseconds': '200'
            }
        })

        self.simulate_press(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 0
        self.simulate_time(timedelta(seconds=0.3))
        assert len(self.calls) == 1
        self.simulate_release(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 1

    def test_held_less_than_short(self):
        """Test a hold that is short enough."""
        self.setup_automation({
            'platform': 'litejet',
            'number': ENTITY_OTHER_SWITCH_NUMBER,
            'held_less_than': {
                'milliseconds': '200'
            }
        })

        self.simulate_press(ENTITY_OTHER_SWITCH_NUMBER)
        self.simulate_time(timedelta(seconds=0.1))
        assert len(self.calls) == 0
        self.simulate_release(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 1

    def test_held_less_than_long(self):
        """Test a hold that is too long."""
        self.setup_automation({
            'platform': 'litejet',
            'number': ENTITY_OTHER_SWITCH_NUMBER,
            'held_less_than': {
                'milliseconds': '200'
            }
        })

        self.simulate_press(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 0
        self.simulate_time(timedelta(seconds=0.3))
        assert len(self.calls) == 0
        self.simulate_release(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 0

    def test_held_in_range_short(self):
        """Test an in-range trigger with a too short hold."""
        self.setup_automation({
            'platform': 'litejet',
            'number': ENTITY_OTHER_SWITCH_NUMBER,
            'held_more_than': {
                'milliseconds': '100'
            },
            'held_less_than': {
                'milliseconds': '300'
            }
        })

        self.simulate_press(ENTITY_OTHER_SWITCH_NUMBER)
        self.simulate_time(timedelta(seconds=0.05))
        self.simulate_release(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 0

    def test_held_in_range_just_right(self):
        """Test an in-range trigger with a just right hold."""
        self.setup_automation({
            'platform': 'litejet',
            'number': ENTITY_OTHER_SWITCH_NUMBER,
            'held_more_than': {
                'milliseconds': '100'
            },
            'held_less_than': {
                'milliseconds': '300'
            }
        })

        self.simulate_press(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 0
        self.simulate_time(timedelta(seconds=0.2))
        assert len(self.calls) == 0
        self.simulate_release(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 1

    def test_held_in_range_long(self):
        """Test an in-range trigger with a too long hold."""
        self.setup_automation({
            'platform': 'litejet',
            'number': ENTITY_OTHER_SWITCH_NUMBER,
            'held_more_than': {
                'milliseconds': '100'
            },
            'held_less_than': {
                'milliseconds': '300'
            }
        })

        self.simulate_press(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 0
        self.simulate_time(timedelta(seconds=0.4))
        assert len(self.calls) == 0
        self.simulate_release(ENTITY_OTHER_SWITCH_NUMBER)
        assert len(self.calls) == 0

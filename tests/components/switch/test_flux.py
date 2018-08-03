"""The tests for the Flux switch platform."""
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.components import switch, light
from homeassistant.const import CONF_PLATFORM, STATE_ON, SERVICE_TURN_ON
import homeassistant.loader as loader
import homeassistant.util.dt as dt_util

from tests.common import (
    assert_setup_component, get_test_home_assistant, fire_time_changed,
    mock_service)


class TestSwitchFlux(unittest.TestCase):
    """Test the Flux switch platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_valid_config(self):
        """Test configuration."""
        assert setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'flux',
                'name': 'flux',
                'lights': ['light.desk', 'light.lamp'],
            }
        })

    def test_valid_config_with_info(self):
        """Test configuration."""
        assert setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'flux',
                'name': 'flux',
                'lights': ['light.desk', 'light.lamp'],
                'stop_time': '22:59',
                'start_time': '7:22',
                'start_colortemp': '1000',
                'sunset_colortemp': '2000',
                'stop_colortemp': '4000'
            }
        })

    def test_valid_config_no_name(self):
        """Test configuration."""
        with assert_setup_component(1, 'switch'):
            assert setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'flux',
                    'lights': ['light.desk', 'light.lamp']
                }
            })

    def test_invalid_config_no_lights(self):
        """Test configuration."""
        with assert_setup_component(0, 'switch'):
            assert setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'flux',
                    'name': 'flux'
                }
            })

    def test_flux_when_switch_is_off(self):
        """Test the flux switch when it is off."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=10, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id]
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        self.assertEqual(0, len(turn_on_calls))

    def test_flux_before_sunrise(self):
        """Test the flux switch before sunrise."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=2, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id]
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 112)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.606, 0.379])

    # pylint: disable=invalid-name
    def test_flux_after_sunrise_before_sunset(self):
        """Test the flux switch after sunrise and before sunset."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=8, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id]
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 173)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.439, 0.37])

    # pylint: disable=invalid-name
    def test_flux_after_sunset_before_stop(self):
        """Test the flux switch after sunset and before stop."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=17, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'stop_time': '22:00'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 146)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.506, 0.385])

    # pylint: disable=invalid-name
    def test_flux_after_stop_before_sunrise(self):
        """Test the flux switch after stop and before sunrise."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=23, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id]
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 112)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.606, 0.379])

    # pylint: disable=invalid-name
    def test_flux_with_custom_start_stop_times(self):
        """Test the flux with custom start and stop times."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=17, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'start_time': '6:00',
                        'stop_time': '23:30'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 147)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.504, 0.385])

    def test_flux_before_sunrise_stop_next_day(self):
        """Test the flux switch before sunrise.

        This test has the stop_time on the next day (after midnight).
        """
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=2, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'stop_time': '01:00'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 112)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.606, 0.379])

    # pylint: disable=invalid-name
    def test_flux_after_sunrise_before_sunset_stop_next_day(self):
        """
        Test the flux switch after sunrise and before sunset.

        This test has the stop_time on the next day (after midnight).
        """
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=8, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'stop_time': '01:00'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 173)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.439, 0.37])

    # pylint: disable=invalid-name
    def test_flux_after_sunset_before_midnight_stop_next_day(self):
        """Test the flux switch after sunset and before stop.

        This test has the stop_time on the next day (after midnight).
        """
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=23, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'stop_time': '01:00'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 119)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.588, 0.386])

    # pylint: disable=invalid-name
    def test_flux_after_sunset_after_midnight_stop_next_day(self):
        """Test the flux switch after sunset and before stop.

        This test has the stop_time on the next day (after midnight).
        """
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=00, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'stop_time': '01:00'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 114)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.601, 0.382])

    # pylint: disable=invalid-name
    def test_flux_after_stop_before_sunrise_stop_next_day(self):
        """Test the flux switch after stop and before sunrise.

        This test has the stop_time on the next day (after midnight).
        """
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=2, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'stop_time': '01:00'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 112)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.606, 0.379])

    # pylint: disable=invalid-name
    def test_flux_with_custom_colortemps(self):
        """Test the flux with custom start and stop colortemps."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=17, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'start_colortemp': '1000',
                        'stop_colortemp': '6000',
                        'stop_time': '22:00'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 159)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.469, 0.378])

    # pylint: disable=invalid-name
    def test_flux_with_custom_brightness(self):
        """Test the flux with custom start and stop colortemps."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=17, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'brightness': 255,
                        'stop_time': '22:00'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 255)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.506, 0.385])

    def test_flux_with_multiple_lights(self):
        """Test the flux switch with multiple light entities."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1, dev2, dev3 = platform.DEVICES
        light.turn_on(self.hass, entity_id=dev2.entity_id)
        self.hass.block_till_done()
        light.turn_on(self.hass, entity_id=dev3.entity_id)
        self.hass.block_till_done()

        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        state = self.hass.states.get(dev2.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        state = self.hass.states.get(dev3.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        test_time = dt_util.now().replace(hour=12, minute=0, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                print('sunrise {}'.format(sunrise_time))
                return sunrise_time
            print('sunset {}'.format(sunset_time))
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id,
                                   dev2.entity_id,
                                   dev3.entity_id]
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 163)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.46, 0.376])
        call = turn_on_calls[-2]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 163)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.46, 0.376])
        call = turn_on_calls[-3]
        self.assertEqual(call.data[light.ATTR_BRIGHTNESS], 163)
        self.assertEqual(call.data[light.ATTR_XY_COLOR], [0.46, 0.376])

    def test_flux_with_mired(self):
        """Test the flux switch´s mode mired."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('color_temp'))

        test_time = dt_util.now().replace(hour=8, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'mode': 'mired'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        self.assertEqual(call.data[light.ATTR_COLOR_TEMP], 269)

    def test_flux_with_rgb(self):
        """Test the flux switch´s mode rgb."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1 = platform.DEVICES[0]

        # Verify initial state of light
        state = self.hass.states.get(dev1.entity_id)
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('color_temp'))

        test_time = dt_util.now().replace(hour=8, minute=30, second=0)
        sunset_time = test_time.replace(hour=17, minute=0, second=0)
        sunrise_time = test_time.replace(hour=5, minute=0, second=0)

        def event_date(hass, event, now=None):
            if event == 'sunrise':
                return sunrise_time
            return sunset_time

        with patch('homeassistant.util.dt.now', return_value=test_time):
            with patch('homeassistant.helpers.sun.get_astral_event_date',
                       side_effect=event_date):
                assert setup_component(self.hass, switch.DOMAIN, {
                    switch.DOMAIN: {
                        'platform': 'flux',
                        'name': 'flux',
                        'lights': [dev1.entity_id],
                        'mode': 'rgb'
                    }
                })
                turn_on_calls = mock_service(
                    self.hass, light.DOMAIN, SERVICE_TURN_ON)
                switch.turn_on(self.hass, 'switch.flux')
                self.hass.block_till_done()
                fire_time_changed(self.hass, test_time)
                self.hass.block_till_done()
        call = turn_on_calls[-1]
        rgb = (255, 198, 152)
        rounded_call = tuple(map(round, call.data[light.ATTR_RGB_COLOR]))
        self.assertEqual(rounded_call, rgb)

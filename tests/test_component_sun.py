"""
tests.test_component_sun
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Sun component.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest
from datetime import timedelta

import ephem

import homeassistant as ha
import homeassistant.util.dt as dt_util
import homeassistant.components.sun as sun


class TestSun(unittest.TestCase):
    """ Test the sun module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_is_on(self):
        """ Test is_on method. """
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON)
        self.assertTrue(sun.is_on(self.hass))
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_BELOW_HORIZON)
        self.assertFalse(sun.is_on(self.hass))

    def test_setting_rising(self):
        """ Test retrieving sun setting and rising. """
        # Compare it with the real data
        self.hass.config.latitude = '32.87336'
        self.hass.config.longitude = '117.22743'
        sun.setup(self.hass, None)

        observer = ephem.Observer()
        observer.lat = '32.87336'  # pylint: disable=assigning-non-slot
        observer.long = '117.22743'  # pylint: disable=assigning-non-slot

        utc_now = dt_util.utcnow()
        body_sun = ephem.Sun()  # pylint: disable=no-member
        next_rising_dt = observer.next_rising(
            body_sun, start=utc_now).datetime().replace(tzinfo=dt_util.UTC)
        next_setting_dt = observer.next_setting(
            body_sun, start=utc_now).datetime().replace(tzinfo=dt_util.UTC)

        # Home Assistant strips out microseconds
        # strip it out of the datetime objects
        next_rising_dt = dt_util.strip_microseconds(next_rising_dt)
        next_setting_dt = dt_util.strip_microseconds(next_setting_dt)

        self.assertEqual(next_rising_dt, sun.next_rising_utc(self.hass))
        self.assertEqual(next_setting_dt, sun.next_setting_utc(self.hass))

        # Point it at a state without the proper attributes
        self.hass.states.set(sun.ENTITY_ID, sun.STATE_ABOVE_HORIZON)
        self.assertIsNone(sun.next_rising(self.hass))
        self.assertIsNone(sun.next_setting(self.hass))

        # Point it at a non-existing state
        self.assertIsNone(sun.next_rising(self.hass, 'non.existing'))
        self.assertIsNone(sun.next_setting(self.hass, 'non.existing'))

    def test_state_change(self):
        """ Test if the state changes at next setting/rising. """
        self.hass.config.latitude = '32.87336'
        self.hass.config.longitude = '117.22743'
        sun.setup(self.hass, None)

        if sun.is_on(self.hass):
            test_state = sun.STATE_BELOW_HORIZON
            test_time = sun.next_setting(self.hass)
        else:
            test_state = sun.STATE_ABOVE_HORIZON
            test_time = sun.next_rising(self.hass)

        self.assertIsNotNone(test_time)

        self.hass.bus.fire(ha.EVENT_TIME_CHANGED,
                           {ha.ATTR_NOW: test_time + timedelta(seconds=5)})

        self.hass.pool.block_till_done()

        self.assertEqual(test_state, self.hass.states.get(sun.ENTITY_ID).state)

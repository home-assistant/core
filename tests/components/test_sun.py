"""The tests for the Sun component."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch
from datetime import timedelta, datetime

from homeassistant.setup import setup_component
import homeassistant.core as ha
import homeassistant.util.dt as dt_util
import homeassistant.components.sun as sun

from tests.common import get_test_home_assistant


# pylint: disable=invalid-name
class TestSun(unittest.TestCase):
    """Test the sun module."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setting_rising(self):
        """Test retrieving sun setting and rising."""
        utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            setup_component(self.hass, sun.DOMAIN, {
                sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        self.hass.block_till_done()
        state = self.hass.states.get(sun.ENTITY_ID)

        from astral import Astral

        astral = Astral()
        utc_today = utc_now.date()

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude

        mod = -1
        while True:
            next_dawn = (astral.dawn_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_dawn > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_dusk = (astral.dusk_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_dusk > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_midnight = (astral.solar_midnight_utc(
                utc_today + timedelta(days=mod), longitude))
            if next_midnight > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_noon = (astral.solar_noon_utc(
                utc_today + timedelta(days=mod), longitude))
            if next_noon > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_rising = (astral.sunrise_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_rising > utc_now:
                break
            mod += 1

        mod = -1
        while True:
            next_setting = (astral.sunset_utc(
                utc_today + timedelta(days=mod), latitude, longitude))
            if next_setting > utc_now:
                break
            mod += 1

        self.assertEqual(next_dawn, dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_DAWN]))
        self.assertEqual(next_dusk, dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_DUSK]))
        self.assertEqual(next_midnight, dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_MIDNIGHT]))
        self.assertEqual(next_noon, dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_NOON]))
        self.assertEqual(next_rising, dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_RISING]))
        self.assertEqual(next_setting, dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_SETTING]))

    def test_state_change(self):
        """Test if the state changes at next setting/rising."""
        now = datetime(2016, 6, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=now):
            setup_component(self.hass, sun.DOMAIN, {
                sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        self.hass.block_till_done()

        test_time = dt_util.parse_datetime(
            self.hass.states.get(sun.ENTITY_ID)
            .attributes[sun.STATE_ATTR_NEXT_RISING])
        self.assertIsNotNone(test_time)

        self.assertEqual(sun.STATE_BELOW_HORIZON,
                         self.hass.states.get(sun.ENTITY_ID).state)

        self.hass.bus.fire(ha.EVENT_TIME_CHANGED,
                           {ha.ATTR_NOW: test_time + timedelta(seconds=5)})

        self.hass.block_till_done()

        self.assertEqual(sun.STATE_ABOVE_HORIZON,
                         self.hass.states.get(sun.ENTITY_ID).state)

    def test_norway_in_june(self):
        """Test location in Norway where the sun doesn't set in summer."""
        self.hass.config.latitude = 69.6
        self.hass.config.longitude = 18.8

        june = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=june):
            assert setup_component(self.hass, sun.DOMAIN, {
                sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

        state = self.hass.states.get(sun.ENTITY_ID)
        assert state is not None

        assert dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_RISING]) == \
            datetime(2016, 7, 25, 23, 23, 39, tzinfo=dt_util.UTC)
        assert dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_NEXT_SETTING]) == \
            datetime(2016, 7, 26, 22, 19, 1, tzinfo=dt_util.UTC)

    def test_sunrise_sunset_daylight(self):
        """Test retrieving sunrise, sunset & daylight attributes."""
        utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            setup_component(self.hass, sun.DOMAIN, {
                sun.DOMAIN: {sun.CONF_MONITORED_CONDITIONS: [
                    sun.STATE_ATTR_SUNRISE,
                    sun.STATE_ATTR_SUNSET,
                    sun.STATE_ATTR_DAYLIGHT,
                    sun.STATE_ATTR_PREV_DAYLIGHT,
                    sun.STATE_ATTR_NEXT_DAYLIGHT]}})

        self.hass.block_till_done()
        state = self.hass.states.get(sun.ENTITY_ID)

        from astral import Astral

        astral = Astral()
        utc_today = utc_now.date()

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude

        sunrise = astral.sunrise_utc(utc_today, latitude, longitude)
        sunset = astral.sunset_utc(utc_today, latitude, longitude)
        daylight = astral.daylight_utc(utc_today, latitude, longitude)
        daylight = (daylight[1] - daylight[0]).total_seconds()
        prev_daylight = astral.daylight_utc(
            utc_today + timedelta(days=-1), latitude, longitude)
        prev_daylight = (prev_daylight[1] - prev_daylight[0]).total_seconds()
        next_daylight = astral.daylight_utc(
            utc_today + timedelta(days=1), latitude, longitude)
        next_daylight = (next_daylight[1] - next_daylight[0]).total_seconds()

        self.assertEqual(sunrise, dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_SUNRISE]))
        self.assertEqual(sunset, dt_util.parse_datetime(
            state.attributes[sun.STATE_ATTR_SUNSET]))
        self.assertEqual(daylight, state.attributes[sun.STATE_ATTR_DAYLIGHT])
        self.assertEqual(
            prev_daylight, state.attributes[sun.STATE_ATTR_PREV_DAYLIGHT])
        self.assertEqual(
            next_daylight, state.attributes[sun.STATE_ATTR_NEXT_DAYLIGHT])

    def test_scan_interval(self):
        """Test optional scan_interval."""
        utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            setup_component(self.hass, sun.DOMAIN, {
                sun.DOMAIN: {sun.CONF_SCAN_INTERVAL: '00:10:00'}})
        self.hass.block_till_done()

        state = self.hass.states.get(sun.ENTITY_ID)
        azimuth = state.attributes[sun.STATE_ATTR_AZIMUTH]
        elevation = state.attributes[sun.STATE_ATTR_ELEVATION]

        utc_now += timedelta(minutes=9)
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: utc_now})
        self.hass.block_till_done()

        state = self.hass.states.get(sun.ENTITY_ID)
        self.assertEqual(azimuth, state.attributes[sun.STATE_ATTR_AZIMUTH])
        self.assertEqual(elevation, state.attributes[sun.STATE_ATTR_ELEVATION])

        utc_now += timedelta(minutes=1, seconds=5)
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: utc_now})
        self.hass.block_till_done()

        state = self.hass.states.get(sun.ENTITY_ID)
        self.assertNotEqual(azimuth, state.attributes[sun.STATE_ATTR_AZIMUTH])
        self.assertNotEqual(
            elevation, state.attributes[sun.STATE_ATTR_ELEVATION])

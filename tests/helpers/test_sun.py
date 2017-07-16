"""The tests for the Sun helpers."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch
from datetime import timedelta, datetime

import homeassistant.util.dt as dt_util
import homeassistant.helpers.sun as sun

from tests.common import get_test_home_assistant


# pylint: disable=invalid-name
class TestSun(unittest.TestCase):
    """Test the sun helpers."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_next_events(self):
        """Test retrieving next sun events."""
        utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
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

        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            self.assertEqual(next_dawn, sun.get_astral_event_next(
                self.hass, 'dawn'))
            self.assertEqual(next_dusk, sun.get_astral_event_next(
                self.hass, 'dusk'))
            self.assertEqual(next_midnight, sun.get_astral_event_next(
                self.hass, 'solar_midnight'))
            self.assertEqual(next_noon, sun.get_astral_event_next(
                self.hass, 'solar_noon'))
            self.assertEqual(next_rising, sun.get_astral_event_next(
                self.hass, 'sunrise'))
            self.assertEqual(next_setting, sun.get_astral_event_next(
                self.hass, 'sunset'))

    def test_date_events(self):
        """Test retrieving next sun events."""
        utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        from astral import Astral

        astral = Astral()
        utc_today = utc_now.date()

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude

        dawn = astral.dawn_utc(utc_today, latitude, longitude)
        dusk = astral.dusk_utc(utc_today, latitude, longitude)
        midnight = astral.solar_midnight_utc(utc_today, longitude)
        noon = astral.solar_noon_utc(utc_today, longitude)
        sunrise = astral.sunrise_utc(utc_today, latitude, longitude)
        sunset = astral.sunset_utc(utc_today, latitude, longitude)

        self.assertEqual(dawn, sun.get_astral_event_date(
            self.hass, 'dawn', utc_today))
        self.assertEqual(dusk, sun.get_astral_event_date(
            self.hass, 'dusk', utc_today))
        self.assertEqual(midnight, sun.get_astral_event_date(
            self.hass, 'solar_midnight', utc_today))
        self.assertEqual(noon, sun.get_astral_event_date(
            self.hass, 'solar_noon', utc_today))
        self.assertEqual(sunrise, sun.get_astral_event_date(
            self.hass, 'sunrise', utc_today))
        self.assertEqual(sunset, sun.get_astral_event_date(
            self.hass, 'sunset', utc_today))

    def test_date_events_default_date(self):
        """Test retrieving next sun events."""
        utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        from astral import Astral

        astral = Astral()
        utc_today = utc_now.date()

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude

        dawn = astral.dawn_utc(utc_today, latitude, longitude)
        dusk = astral.dusk_utc(utc_today, latitude, longitude)
        midnight = astral.solar_midnight_utc(utc_today, longitude)
        noon = astral.solar_noon_utc(utc_today, longitude)
        sunrise = astral.sunrise_utc(utc_today, latitude, longitude)
        sunset = astral.sunset_utc(utc_today, latitude, longitude)

        with patch('homeassistant.util.dt.now', return_value=utc_now):
            self.assertEqual(dawn, sun.get_astral_event_date(
                self.hass, 'dawn', utc_today))
            self.assertEqual(dusk, sun.get_astral_event_date(
                self.hass, 'dusk', utc_today))
            self.assertEqual(midnight, sun.get_astral_event_date(
                self.hass, 'solar_midnight', utc_today))
            self.assertEqual(noon, sun.get_astral_event_date(
                self.hass, 'solar_noon', utc_today))
            self.assertEqual(sunrise, sun.get_astral_event_date(
                self.hass, 'sunrise', utc_today))
            self.assertEqual(sunset, sun.get_astral_event_date(
                self.hass, 'sunset', utc_today))

    def test_date_events_accepts_datetime(self):
        """Test retrieving next sun events."""
        utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
        from astral import Astral

        astral = Astral()
        utc_today = utc_now.date()

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude

        dawn = astral.dawn_utc(utc_today, latitude, longitude)
        dusk = astral.dusk_utc(utc_today, latitude, longitude)
        midnight = astral.solar_midnight_utc(utc_today, longitude)
        noon = astral.solar_noon_utc(utc_today, longitude)
        sunrise = astral.sunrise_utc(utc_today, latitude, longitude)
        sunset = astral.sunset_utc(utc_today, latitude, longitude)

        self.assertEqual(dawn, sun.get_astral_event_date(
            self.hass, 'dawn', utc_now))
        self.assertEqual(dusk, sun.get_astral_event_date(
            self.hass, 'dusk', utc_now))
        self.assertEqual(midnight, sun.get_astral_event_date(
            self.hass, 'solar_midnight', utc_now))
        self.assertEqual(noon, sun.get_astral_event_date(
            self.hass, 'solar_noon', utc_now))
        self.assertEqual(sunrise, sun.get_astral_event_date(
            self.hass, 'sunrise', utc_now))
        self.assertEqual(sunset, sun.get_astral_event_date(
            self.hass, 'sunset', utc_now))

    def test_is_up(self):
        """Test retrieving next sun events."""
        utc_now = datetime(2016, 11, 1, 12, 0, 0, tzinfo=dt_util.UTC)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            self.assertFalse(sun.is_up(self.hass))

        utc_now = datetime(2016, 11, 1, 18, 0, 0, tzinfo=dt_util.UTC)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=utc_now):
            self.assertTrue(sun.is_up(self.hass))

    def test_norway_in_june(self):
        """Test location in Norway where the sun doesn't set in summer."""
        self.hass.config.latitude = 69.6
        self.hass.config.longitude = 18.8

        june = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

        print(sun.get_astral_event_date(self.hass, 'sunrise',
                                        datetime(2017, 7, 25)))
        print(sun.get_astral_event_date(self.hass, 'sunset',
                                        datetime(2017, 7, 25)))

        print(sun.get_astral_event_date(self.hass, 'sunrise',
                                        datetime(2017, 7, 26)))
        print(sun.get_astral_event_date(self.hass, 'sunset',
                                        datetime(2017, 7, 26)))

        assert sun.get_astral_event_next(self.hass, 'sunrise', june) == \
            datetime(2016, 7, 25, 23, 23, 39, tzinfo=dt_util.UTC)
        assert sun.get_astral_event_next(self.hass, 'sunset', june) == \
            datetime(2016, 7, 26, 22, 19, 1, tzinfo=dt_util.UTC)
        assert sun.get_astral_event_date(self.hass, 'sunrise', june) is None
        assert sun.get_astral_event_date(self.hass, 'sunset', june) is None

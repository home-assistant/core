"""Test Home Assistant date util methods."""
# pylint: disable=too-many-public-methods
import unittest
from datetime import datetime, timedelta

import homeassistant.util.dt as dt_util

TEST_TIME_ZONE = 'America/Los_Angeles'


class TestDateUtil(unittest.TestCase):
    """Test util date methods."""

    def setUp(self):
        """Setup the tests."""
        self.orig_default_time_zone = dt_util.DEFAULT_TIME_ZONE

    def tearDown(self):
        """Stop everything that was started."""
        dt_util.set_default_time_zone(self.orig_default_time_zone)

    def test_get_time_zone_retrieves_valid_time_zone(self):
        """Test getting a time zone."""
        time_zone = dt_util.get_time_zone(TEST_TIME_ZONE)

        self.assertIsNotNone(time_zone)
        self.assertEqual(TEST_TIME_ZONE, time_zone.zone)

    def test_get_time_zone_returns_none_for_garbage_time_zone(self):
        """Test getting a non existing time zone."""
        time_zone = dt_util.get_time_zone("Non existing time zone")

        self.assertIsNone(time_zone)

    def test_set_default_time_zone(self):
        """Test setting default time zone."""
        time_zone = dt_util.get_time_zone(TEST_TIME_ZONE)

        dt_util.set_default_time_zone(time_zone)

        # We cannot compare the timezones directly because of DST
        self.assertEqual(time_zone.zone, dt_util.now().tzinfo.zone)

    def test_utcnow(self):
        """Test the UTC now method."""
        self.assertAlmostEqual(
            dt_util.utcnow().replace(tzinfo=None),
            datetime.utcnow(),
            delta=timedelta(seconds=1))

    def test_now(self):
        """Test the now method."""
        dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))

        self.assertAlmostEqual(
            dt_util.as_utc(dt_util.now()).replace(tzinfo=None),
            datetime.utcnow(),
            delta=timedelta(seconds=1))

    def test_as_utc_with_naive_object(self):
        """Test the now method."""
        utcnow = datetime.utcnow()

        self.assertEqual(utcnow,
                         dt_util.as_utc(utcnow).replace(tzinfo=None))

    def test_as_utc_with_utc_object(self):
        """Test UTC time with UTC object."""
        utcnow = dt_util.utcnow()

        self.assertEqual(utcnow, dt_util.as_utc(utcnow))

    def test_as_utc_with_local_object(self):
        """Test the UTC time with local object."""
        dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))
        localnow = dt_util.now()
        utcnow = dt_util.as_utc(localnow)

        self.assertEqual(localnow, utcnow)
        self.assertNotEqual(localnow.tzinfo, utcnow.tzinfo)

    def test_as_local_with_naive_object(self):
        """Test local time with native object."""
        now = dt_util.now()
        self.assertAlmostEqual(
            now, dt_util.as_local(datetime.utcnow()),
            delta=timedelta(seconds=1))

    def test_as_local_with_local_object(self):
        """Test local with local object."""
        now = dt_util.now()
        self.assertEqual(now, now)

    def test_as_local_with_utc_object(self):
        """Test local time with UTC object."""
        dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))

        utcnow = dt_util.utcnow()
        localnow = dt_util.as_local(utcnow)

        self.assertEqual(localnow, utcnow)
        self.assertNotEqual(localnow.tzinfo, utcnow.tzinfo)

    def test_utc_from_timestamp(self):
        """Test utc_from_timestamp method."""
        self.assertEqual(
            datetime(1986, 7, 9, tzinfo=dt_util.UTC),
            dt_util.utc_from_timestamp(521251200))

    def test_datetime_to_str(self):
        """Test datetime_to_str."""
        self.assertEqual(
            "12:00:00 09-07-1986",
            dt_util.datetime_to_str(datetime(1986, 7, 9, 12, 0, 0)))

    def test_datetime_to_local_str(self):
        """Test datetime_to_local_str."""
        self.assertEqual(
            dt_util.datetime_to_str(dt_util.now()),
            dt_util.datetime_to_local_str(dt_util.utcnow()))

    def test_str_to_datetime_converts_correctly(self):
        """Test str_to_datetime converts strings."""
        self.assertEqual(
            datetime(1986, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC),
            dt_util.str_to_datetime("12:00:00 09-07-1986"))

    def test_str_to_datetime_returns_none_for_incorrect_format(self):
        """Test str_to_datetime returns None if incorrect format."""
        self.assertIsNone(dt_util.str_to_datetime("not a datetime string"))

    def test_strip_microseconds(self):
        """Test the now method."""
        test_time = datetime(2015, 1, 1, microsecond=5000)

        self.assertNotEqual(0, test_time.microsecond)
        self.assertEqual(0, dt_util.strip_microseconds(test_time).microsecond)

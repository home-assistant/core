"""Test Home Assistant date util methods."""
import unittest
from datetime import datetime, timedelta

import homeassistant.util.dt as dt_util

TEST_TIME_ZONE = 'America/Los_Angeles'


class TestDateUtil(unittest.TestCase):
    """Test util date methods."""

    def setUp(self):
        """Set up the tests."""
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

    def test_as_timestamp(self):
        """Test as_timestamp method."""
        ts = 1462401234
        utc_dt = dt_util.utc_from_timestamp(ts)
        self.assertEqual(ts, dt_util.as_timestamp(utc_dt))
        utc_iso = utc_dt.isoformat()
        self.assertEqual(ts, dt_util.as_timestamp(utc_iso))

        # confirm the ability to handle a string passed in
        delta = dt_util.as_timestamp("2016-01-01 12:12:12")
        delta -= dt_util.as_timestamp("2016-01-01 12:12:11")
        self.assertEqual(1, delta)

    def test_parse_datetime_converts_correctly(self):
        """Test parse_datetime converts strings."""
        assert \
            datetime(1986, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC) == \
            dt_util.parse_datetime("1986-07-09T12:00:00Z")

        utcnow = dt_util.utcnow()

        assert utcnow == dt_util.parse_datetime(utcnow.isoformat())

    def test_parse_datetime_returns_none_for_incorrect_format(self):
        """Test parse_datetime returns None if incorrect format."""
        self.assertIsNone(dt_util.parse_datetime("not a datetime string"))

    def test_get_age(self):
        """Test get_age."""
        diff = dt_util.now() - timedelta(seconds=0)
        self.assertEqual(dt_util.get_age(diff), "0 seconds")

        diff = dt_util.now() - timedelta(seconds=1)
        self.assertEqual(dt_util.get_age(diff), "1 second")

        diff = dt_util.now() - timedelta(seconds=30)
        self.assertEqual(dt_util.get_age(diff), "30 seconds")

        diff = dt_util.now() - timedelta(minutes=5)
        self.assertEqual(dt_util.get_age(diff), "5 minutes")

        diff = dt_util.now() - timedelta(minutes=1)
        self.assertEqual(dt_util.get_age(diff), "1 minute")

        diff = dt_util.now() - timedelta(minutes=300)
        self.assertEqual(dt_util.get_age(diff), "5 hours")

        diff = dt_util.now() - timedelta(minutes=320)
        self.assertEqual(dt_util.get_age(diff), "5 hours")

        diff = dt_util.now() - timedelta(minutes=2*60*24)
        self.assertEqual(dt_util.get_age(diff), "2 days")

        diff = dt_util.now() - timedelta(minutes=32*60*24)
        self.assertEqual(dt_util.get_age(diff), "1 month")

        diff = dt_util.now() - timedelta(minutes=365*60*24)
        self.assertEqual(dt_util.get_age(diff), "1 year")

    def test_parse_time_expression(self):
        """Test parse_time_expression."""
        self.assertEqual(
            [x for x in range(60)],
            dt_util.parse_time_expression('*', 0, 59)
        )
        self.assertEqual(
            [x for x in range(60)],
            dt_util.parse_time_expression(None, 0, 59)
        )

        self.assertEqual(
            [x for x in range(0, 60, 5)],
            dt_util.parse_time_expression('/5', 0, 59)
        )

        self.assertEqual(
            [1, 2, 3],
            dt_util.parse_time_expression([2, 1, 3], 0, 59)
        )

        self.assertEqual(
            [x for x in range(24)],
            dt_util.parse_time_expression('*', 0, 23)
        )

        self.assertEqual(
            [42],
            dt_util.parse_time_expression(42, 0, 59)
        )

        self.assertRaises(ValueError, dt_util.parse_time_expression, 61, 0, 60)

    def test_find_next_time_expression_time_basic(self):
        """Test basic stuff for find_next_time_expression_time."""
        def find(dt, hour, minute, second):
            """Call test_find_next_time_expression_time."""
            seconds = dt_util.parse_time_expression(second, 0, 59)
            minutes = dt_util.parse_time_expression(minute, 0, 59)
            hours = dt_util.parse_time_expression(hour, 0, 23)

            return dt_util.find_next_time_expression_time(
                dt, seconds, minutes, hours)

        self.assertEqual(
            datetime(2018, 10, 7, 10, 30, 0),
            find(datetime(2018, 10, 7, 10, 20, 0), '*', '/30', 0)
        )

        self.assertEqual(
            datetime(2018, 10, 7, 10, 30, 0),
            find(datetime(2018, 10, 7, 10, 30, 0), '*', '/30', 0)
        )

        self.assertEqual(
            datetime(2018, 10, 7, 12, 30, 30),
            find(datetime(2018, 10, 7, 10, 30, 0), '/3', '/30', [30, 45])
        )

        self.assertEqual(
            datetime(2018, 10, 8, 5, 0, 0),
            find(datetime(2018, 10, 7, 10, 30, 0), 5, 0, 0)
        )

    def test_find_next_time_expression_time_dst(self):
        """Test daylight saving time for find_next_time_expression_time."""
        tz = dt_util.get_time_zone('Europe/Vienna')
        dt_util.set_default_time_zone(tz)

        def find(dt, hour, minute, second):
            """Call test_find_next_time_expression_time."""
            seconds = dt_util.parse_time_expression(second, 0, 59)
            minutes = dt_util.parse_time_expression(minute, 0, 59)
            hours = dt_util.parse_time_expression(hour, 0, 23)

            return dt_util.find_next_time_expression_time(
                dt, seconds, minutes, hours)

        # Entering DST, clocks are rolled forward
        self.assertEqual(
            tz.localize(datetime(2018, 3, 26, 2, 30, 0)),
            find(tz.localize(datetime(2018, 3, 25, 1, 50, 0)), 2, 30, 0)
        )

        self.assertEqual(
            tz.localize(datetime(2018, 3, 26, 2, 30, 0)),
            find(tz.localize(datetime(2018, 3, 25, 3, 50, 0)), 2, 30, 0)
        )

        self.assertEqual(
            tz.localize(datetime(2018, 3, 26, 2, 30, 0)),
            find(tz.localize(datetime(2018, 3, 26, 1, 50, 0)), 2, 30, 0)
        )

        # Leaving DST, clocks are rolled back
        self.assertEqual(
            tz.localize(datetime(2018, 10, 28, 2, 30, 0), is_dst=False),
            find(tz.localize(datetime(2018, 10, 28, 2, 5, 0), is_dst=False),
                 2, 30, 0)
        )

        self.assertEqual(
            tz.localize(datetime(2018, 10, 28, 2, 30, 0), is_dst=False),
            find(tz.localize(datetime(2018, 10, 28, 2, 55, 0), is_dst=True),
                 2, 30, 0)
        )

        self.assertEqual(
            tz.localize(datetime(2018, 10, 28, 4, 30, 0), is_dst=False),
            find(tz.localize(datetime(2018, 10, 28, 2, 55, 0), is_dst=True),
                 4, 30, 0)
        )

        self.assertEqual(
            tz.localize(datetime(2018, 10, 28, 2, 30, 0), is_dst=True),
            find(tz.localize(datetime(2018, 10, 28, 2, 5, 0), is_dst=True),
                 2, 30, 0)
        )

        self.assertEqual(
            tz.localize(datetime(2018, 10, 29, 2, 30, 0)),
            find(tz.localize(datetime(2018, 10, 28, 2, 55, 0), is_dst=False),
                 2, 30, 0)
        )

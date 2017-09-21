"""Test Home Assistant util methods."""
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

from homeassistant import util
import homeassistant.util.dt as dt_util


class TestUtil(unittest.TestCase):
    """Test util methods."""

    def test_sanitize_filename(self):
        """Test sanitize_filename."""
        self.assertEqual("test", util.sanitize_filename("test"))
        self.assertEqual("test", util.sanitize_filename("/test"))
        self.assertEqual("test", util.sanitize_filename("..test"))
        self.assertEqual("test", util.sanitize_filename("\\test"))
        self.assertEqual("test", util.sanitize_filename("\\../test"))

    def test_sanitize_path(self):
        """Test sanitize_path."""
        self.assertEqual("test/path", util.sanitize_path("test/path"))
        self.assertEqual("test/path", util.sanitize_path("~test/path"))
        self.assertEqual("//test/path",
                         util.sanitize_path("~/../test/path"))

    def test_slugify(self):
        """Test slugify."""
        self.assertEqual("test", util.slugify("T-!@#$!#@$!$est"))
        self.assertEqual("test_more", util.slugify("Test More"))
        self.assertEqual("test_more", util.slugify("Test_(More)"))
        self.assertEqual("test_more", util.slugify("Tèst_Mörê"))
        self.assertEqual("b827eb000000", util.slugify("B8:27:EB:00:00:00"))
        self.assertEqual("testcom", util.slugify("test.com"))
        self.assertEqual("greg_phone__exp_wayp1",
                         util.slugify("greg_phone - exp_wayp1"))
        self.assertEqual("we_are_we_are_a_test_calendar",
                         util.slugify("We are, we are, a... Test Calendar"))
        self.assertEqual("test_aouss_aou", util.slugify("Tèst_äöüß_ÄÖÜ"))

    def test_repr_helper(self):
        """Test repr_helper."""
        self.assertEqual("A", util.repr_helper("A"))
        self.assertEqual("5", util.repr_helper(5))
        self.assertEqual("True", util.repr_helper(True))
        self.assertEqual("test=1",
                         util.repr_helper({"test": 1}))
        self.assertEqual("1986-07-09T12:00:00+00:00",
                         util.repr_helper(datetime(1986, 7, 9, 12, 0, 0)))

    def test_convert(self):
        """Test convert."""
        self.assertEqual(5, util.convert("5", int))
        self.assertEqual(5.0, util.convert("5", float))
        self.assertEqual(True, util.convert("True", bool))
        self.assertEqual(1, util.convert("NOT A NUMBER", int, 1))
        self.assertEqual(1, util.convert(None, int, 1))
        self.assertEqual(1, util.convert(object, int, 1))

    def test_ensure_unique_string(self):
        """Test ensure_unique_string."""
        self.assertEqual(
            "Beer_3",
            util.ensure_unique_string("Beer", ["Beer", "Beer_2"]))
        self.assertEqual(
            "Beer",
            util.ensure_unique_string("Beer", ["Wine", "Soda"]))

    def test_ordered_enum(self):
        """Test the ordered enum class."""
        class TestEnum(util.OrderedEnum):
            """Test enum that can be ordered."""

            FIRST = 1
            SECOND = 2
            THIRD = 3

        self.assertTrue(TestEnum.SECOND >= TestEnum.FIRST)
        self.assertTrue(TestEnum.SECOND >= TestEnum.SECOND)
        self.assertFalse(TestEnum.SECOND >= TestEnum.THIRD)

        self.assertTrue(TestEnum.SECOND > TestEnum.FIRST)
        self.assertFalse(TestEnum.SECOND > TestEnum.SECOND)
        self.assertFalse(TestEnum.SECOND > TestEnum.THIRD)

        self.assertFalse(TestEnum.SECOND <= TestEnum.FIRST)
        self.assertTrue(TestEnum.SECOND <= TestEnum.SECOND)
        self.assertTrue(TestEnum.SECOND <= TestEnum.THIRD)

        self.assertFalse(TestEnum.SECOND < TestEnum.FIRST)
        self.assertFalse(TestEnum.SECOND < TestEnum.SECOND)
        self.assertTrue(TestEnum.SECOND < TestEnum.THIRD)

        # Python will raise a TypeError if the <, <=, >, >= methods
        # raise a NotImplemented error.
        self.assertRaises(TypeError,
                          lambda x, y: x < y, TestEnum.FIRST, 1)

        self.assertRaises(TypeError,
                          lambda x, y: x <= y, TestEnum.FIRST, 1)

        self.assertRaises(TypeError,
                          lambda x, y: x > y, TestEnum.FIRST, 1)

        self.assertRaises(TypeError,
                          lambda x, y: x >= y, TestEnum.FIRST, 1)

    def test_ordered_set(self):
        """Test ordering of set."""
        set1 = util.OrderedSet([1, 2, 3, 4])
        set2 = util.OrderedSet([3, 4, 5])

        self.assertEqual(4, len(set1))
        self.assertEqual(3, len(set2))

        self.assertIn(1, set1)
        self.assertIn(2, set1)
        self.assertIn(3, set1)
        self.assertIn(4, set1)
        self.assertNotIn(5, set1)

        self.assertNotIn(1, set2)
        self.assertNotIn(2, set2)
        self.assertIn(3, set2)
        self.assertIn(4, set2)
        self.assertIn(5, set2)

        set1.add(5)
        self.assertIn(5, set1)

        set1.discard(5)
        self.assertNotIn(5, set1)

        # Try again while key is not in
        set1.discard(5)
        self.assertNotIn(5, set1)

        self.assertEqual([1, 2, 3, 4], list(set1))
        self.assertEqual([4, 3, 2, 1], list(reversed(set1)))

        self.assertEqual(1, set1.pop(False))
        self.assertEqual([2, 3, 4], list(set1))

        self.assertEqual(4, set1.pop())
        self.assertEqual([2, 3], list(set1))

        self.assertEqual('OrderedSet()', str(util.OrderedSet()))
        self.assertEqual('OrderedSet([2, 3])', str(set1))

        self.assertEqual(set1, util.OrderedSet([2, 3]))
        self.assertNotEqual(set1, util.OrderedSet([3, 2]))
        self.assertEqual(set1, set([2, 3]))
        self.assertEqual(set1, {3, 2})
        self.assertEqual(set1, [2, 3])
        self.assertEqual(set1, [3, 2])
        self.assertNotEqual(set1, {2})

        set3 = util.OrderedSet(set1)
        set3.update(set2)

        self.assertEqual([3, 4, 5, 2], set3)
        self.assertEqual([3, 4, 5, 2], set1 | set2)
        self.assertEqual([3], set1 & set2)
        self.assertEqual([2], set1 - set2)

        set1.update([1, 2], [5, 6])
        self.assertEqual([2, 3, 1, 5, 6], set1)

    def test_throttle(self):
        """Test the add cooldown decorator."""
        calls1 = []
        calls2 = []

        @util.Throttle(timedelta(seconds=4))
        def test_throttle1():
            calls1.append(1)

        @util.Throttle(timedelta(seconds=4), timedelta(seconds=2))
        def test_throttle2():
            calls2.append(1)

        now = dt_util.utcnow()
        plus3 = now + timedelta(seconds=3)
        plus5 = plus3 + timedelta(seconds=2)

        # Call first time and ensure methods got called
        test_throttle1()
        test_throttle2()

        self.assertEqual(1, len(calls1))
        self.assertEqual(1, len(calls2))

        # Call second time. Methods should not get called
        test_throttle1()
        test_throttle2()

        self.assertEqual(1, len(calls1))
        self.assertEqual(1, len(calls2))

        # Call again, overriding throttle, only first one should fire
        test_throttle1(no_throttle=True)
        test_throttle2(no_throttle=True)

        self.assertEqual(2, len(calls1))
        self.assertEqual(1, len(calls2))

        with patch('homeassistant.util.utcnow', return_value=plus3):
            test_throttle1()
            test_throttle2()

        self.assertEqual(2, len(calls1))
        self.assertEqual(1, len(calls2))

        with patch('homeassistant.util.utcnow', return_value=plus5):
            test_throttle1()
            test_throttle2()

        self.assertEqual(3, len(calls1))
        self.assertEqual(2, len(calls2))

    def test_throttle_per_instance(self):
        """Test that the throttle method is done per instance of a class."""
        class Tester(object):
            """A tester class for the throttle."""

            @util.Throttle(timedelta(seconds=1))
            def hello(self):
                """Test the throttle."""
                return True

        self.assertTrue(Tester().hello())
        self.assertTrue(Tester().hello())

    def test_throttle_on_method(self):
        """Test that throttle works when wrapping a method."""
        class Tester(object):
            """A tester class for the throttle."""

            def hello(self):
                """Test the throttle."""
                return True

        tester = Tester()
        throttled = util.Throttle(timedelta(seconds=1))(tester.hello)

        self.assertTrue(throttled())
        self.assertIsNone(throttled())

    def test_throttle_on_two_method(self):
        """Test that throttle works when wrapping two methods."""
        class Tester(object):
            """A test class for the throttle."""

            @util.Throttle(timedelta(seconds=1))
            def hello(self):
                """Test the throttle."""
                return True

            @util.Throttle(timedelta(seconds=1))
            def goodbye(self):
                """Test the throttle."""
                return True

        tester = Tester()

        self.assertTrue(tester.hello())
        self.assertTrue(tester.goodbye())

"""
tests.test_util
~~~~~~~~~~~~~~~~~

Tests Home Assistant util methods.
"""
# pylint: disable=too-many-public-methods
import unittest
import time
from datetime import datetime, timedelta

import homeassistant.util as util


class TestUtil(unittest.TestCase):
    """ Tests util methods. """
    def test_sanitize_filename(self):
        """ Test sanitize_filename. """
        self.assertEqual("test", util.sanitize_filename("test"))
        self.assertEqual("test", util.sanitize_filename("/test"))
        self.assertEqual("test", util.sanitize_filename("..test"))
        self.assertEqual("test", util.sanitize_filename("\\test"))
        self.assertEqual("test", util.sanitize_filename("\\../test"))

    def test_sanitize_path(self):
        """ Test sanitize_path. """
        self.assertEqual("test/path", util.sanitize_path("test/path"))
        self.assertEqual("test/path", util.sanitize_path("~test/path"))
        self.assertEqual("//test/path",
                         util.sanitize_path("~/../test/path"))

    def test_slugify(self):
        """ Test slugify. """
        self.assertEqual("Test", util.slugify("T-!@#$!#@$!$est"))
        self.assertEqual("Test_More", util.slugify("Test More"))
        self.assertEqual("Test_More", util.slugify("Test_(More)"))

    def test_split_entity_id(self):
        """ Test split_entity_id. """
        self.assertEqual(['domain', 'object_id'],
                         util.split_entity_id('domain.object_id'))

    def test_repr_helper(self):
        """ Test repr_helper. """
        self.assertEqual("A", util.repr_helper("A"))
        self.assertEqual("5", util.repr_helper(5))
        self.assertEqual("True", util.repr_helper(True))
        self.assertEqual("test=1",
                         util.repr_helper({"test": 1}))
        self.assertEqual("12:00:00 09-07-1986",
                         util.repr_helper(datetime(1986, 7, 9, 12, 0, 0)))

    # pylint: disable=invalid-name
    def test_color_RGB_to_xy(self):
        """ Test color_RGB_to_xy. """
        self.assertEqual((0, 0), util.color_RGB_to_xy(0, 0, 0))
        self.assertEqual((0.3127159072215825, 0.3290014805066623),
                         util.color_RGB_to_xy(255, 255, 255))

        self.assertEqual((0.15001662234042554, 0.060006648936170214),
                         util.color_RGB_to_xy(0, 0, 255))

        self.assertEqual((0.3, 0.6), util.color_RGB_to_xy(0, 255, 0))

        self.assertEqual((0.6400744994567747, 0.3299705106316933),
                         util.color_RGB_to_xy(255, 0, 0))

    def test_convert(self):
        """ Test convert. """
        self.assertEqual(5, util.convert("5", int))
        self.assertEqual(5.0, util.convert("5", float))
        self.assertEqual(True, util.convert("True", bool))
        self.assertEqual(1, util.convert("NOT A NUMBER", int, 1))
        self.assertEqual(1, util.convert(None, int, 1))

    def test_ensure_unique_string(self):
        """ Test ensure_unique_string. """
        self.assertEqual(
            "Beer_3",
            util.ensure_unique_string("Beer", ["Beer", "Beer_2"]))
        self.assertEqual(
            "Beer",
            util.ensure_unique_string("Beer", ["Wine", "Soda"]))

    def test_ordered_enum(self):
        """ Test the ordered enum class. """

        class TestEnum(util.OrderedEnum):
            """ Test enum that can be ordered. """
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
        """ Test the add cooldown decorator. """
        calls1 = []

        @util.Throttle(timedelta(milliseconds=500))
        def test_throttle1():
            calls1.append(1)

        calls2 = []

        @util.Throttle(
            timedelta(milliseconds=500), timedelta(milliseconds=250))
        def test_throttle2():
            calls2.append(1)

        # Ensure init is ok
        self.assertEqual(0, len(calls1))
        self.assertEqual(0, len(calls2))

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

        # Sleep past the no throttle interval for throttle2
        time.sleep(.3)

        test_throttle1()
        test_throttle2()

        self.assertEqual(2, len(calls1))
        self.assertEqual(1, len(calls2))

        test_throttle1(no_throttle=True)
        test_throttle2(no_throttle=True)

        self.assertEqual(3, len(calls1))
        self.assertEqual(2, len(calls2))

        time.sleep(.5)

        test_throttle1()
        test_throttle2()

        self.assertEqual(4, len(calls1))
        self.assertEqual(3, len(calls2))

"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""
# pylint: disable=too-many-public-methods
import unittest
from datetime import datetime

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

    def test_datetime_to_str(self):
        """ Test datetime_to_str. """
        self.assertEqual("12:00:00 09-07-1986",
                         util.datetime_to_str(datetime(1986, 7, 9, 12, 0, 0)))

    def test_str_to_datetime(self):
        """ Test str_to_datetime. """
        self.assertEqual(datetime(1986, 7, 9, 12, 0, 0),
                         util.str_to_datetime("12:00:00 09-07-1986"))

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

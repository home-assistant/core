"""Tests for homeassistant.util.retry."""
import unittest

from homeassistant.util.retry import retry


class Subject(object):
    """Helper class that will raise exception."""

    def __init__(self, count, exception):
        """Constructor."""
        self.count = count
        self.exception = exception

    def run(self):
        """Raise exception after count tries."""
        if self.count > 0:
            self.count -= 1
            raise self.exception
        return True


class TestRetry(unittest.TestCase):
    """Main test class."""

    def test_no_params(self):
        """Test decorator with default parameters."""
        @retry()
        def func(subject):
            """Decorated by default."""
            return subject.run()

        self.assertTrue(func(Subject(4, RuntimeError)))

        with self.assertRaises(RuntimeError):
            func(Subject(5, RuntimeError))

    def test_10_retries(self):
        """Test decorator with custom number of retries."""
        @retry(10)
        def func(subject):
            """Decorated with specific count."""
            return subject.run()

        self.assertTrue(func(Subject(9, RuntimeError)))

        with self.assertRaises(RuntimeError):
            func(Subject(10, RuntimeError))

    def test_specific_exception(self):
        """Test decorator for specific exception."""
        @retry(exc_type=TypeError)
        def func(subject):
            """Decorated with specific exception."""
            return subject.run()

        self.assertTrue(func(Subject(4, TypeError)))

        with self.assertRaises(RuntimeError):
            func(Subject(1, RuntimeError))

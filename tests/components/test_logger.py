"""The tests for the Logger component."""
from collections import namedtuple
import logging
import unittest

from homeassistant.setup import setup_component
from homeassistant.components import logger

from tests.common import get_test_home_assistant

RECORD = namedtuple('record', ('name', 'levelno'))

NO_DEFAULT_CONFIG = {'logger': {}}
NO_LOGS_CONFIG = {'logger': {'default': 'info'}}
TEST_CONFIG = {
    'logger': {
        'default': 'warning',
        'logs': {'test': 'info'}
    }
}


class TestUpdater(unittest.TestCase):
    """Test logger component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.log_filter = None

    def tearDown(self):
        """Stop everything that was started."""
        del logging.root.handlers[-1]
        self.hass.stop()

    def setup_logger(self, config):
        """Set up logger and save log filter."""
        setup_component(self.hass, logger.DOMAIN, config)
        self.log_filter = logging.root.handlers[-1].filters[0]

    def assert_logged(self, name, level):
        """Assert that a certain record was logged."""
        assert self.log_filter.filter(RECORD(name, level))

    def assert_not_logged(self, name, level):
        """Assert that a certain record was not logged."""
        assert not self.log_filter.filter(RECORD(name, level))

    def test_logger_setup(self):
        """Use logger to create a logging filter."""
        self.setup_logger(TEST_CONFIG)

        assert len(logging.root.handlers) > 0
        handler = logging.root.handlers[-1]

        assert len(handler.filters) == 1
        log_filter = handler.filters[0].logfilter

        assert log_filter['default'] == logging.WARNING
        assert log_filter['logs']['test'] == logging.INFO

    def test_logger_test_filters(self):
        """Test resulting filter operation."""
        self.setup_logger(TEST_CONFIG)

        # Blocked default record
        self.assert_not_logged('asdf', logging.DEBUG)

        # Allowed default record
        self.assert_logged('asdf', logging.WARNING)

        # Blocked named record
        self.assert_not_logged('test', logging.DEBUG)

        # Allowed named record
        self.assert_logged('test', logging.INFO)

    def test_set_filter_empty_config(self):
        """Test change log level from empty configuration."""
        self.setup_logger(NO_LOGS_CONFIG)

        self.assert_not_logged('test', logging.DEBUG)

        self.hass.services.call(
            logger.DOMAIN, 'set_level', {'test': 'debug'})
        self.hass.block_till_done()

        self.assert_logged('test', logging.DEBUG)

    def test_set_filter(self):
        """Test change log level of existing filter."""
        self.setup_logger(TEST_CONFIG)

        self.assert_not_logged('asdf', logging.DEBUG)
        self.assert_logged('dummy', logging.WARNING)

        self.hass.services.call(logger.DOMAIN, 'set_level',
                                {'asdf': 'debug', 'dummy': 'info'})
        self.hass.block_till_done()

        self.assert_logged('asdf', logging.DEBUG)
        self.assert_logged('dummy', logging.WARNING)

    def test_set_default_filter_empty_config(self):
        """Test change default log level from empty configuration."""
        self.setup_logger(NO_DEFAULT_CONFIG)

        self.assert_logged('test', logging.DEBUG)

        self.hass.services.call(
            logger.DOMAIN, 'set_default_level', {'level': 'warning'})
        self.hass.block_till_done()

        self.assert_not_logged('test', logging.DEBUG)

    def test_set_default_filter(self):
        """Test change default log level with existing default."""
        self.setup_logger(TEST_CONFIG)

        self.assert_not_logged('asdf', logging.DEBUG)
        self.assert_logged('dummy', logging.WARNING)

        self.hass.services.call(
            logger.DOMAIN, 'set_default_level', {'level': 'debug'})
        self.hass.block_till_done()

        self.assert_logged('asdf', logging.DEBUG)
        self.assert_logged('dummy', logging.WARNING)

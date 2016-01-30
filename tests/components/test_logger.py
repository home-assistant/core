"""
tests.test_logger
~~~~~~~~~~~~~~~~~~

Tests logger component.
"""
import logging
import unittest

from homeassistant.components import logger


class TestUpdater(unittest.TestCase):
    """ Test logger component. """

    def test_logger(self):
        """ Uses logger to create a logging filter """
        config = {'logger':
                  {'default': 'warning',
                   'logs': {'test': 'info'}}}

        logger.setup(None, config)

        self.assertTrue(len(logging.root.handlers) > 0)
        handler = logging.root.handlers[-1]

        self.assertEqual(len(handler.filters), 1)
        log_filter = handler.filters[0].logfilter

        self.assertEqual(log_filter['default'], logging.WARNING)
        self.assertEqual(log_filter['logs']['test'], logging.INFO)

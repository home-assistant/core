"""
tests.helpers.test_service
~~~~~~~~~~~~~~~~~~~~~~~~~~

Test service helpers.
"""
from datetime import timedelta
import unittest
from unittest.mock import patch

import homeassistant.core as ha
from homeassistant.const import SERVICE_TURN_ON
from homeassistant.helpers import service

from tests.common import get_test_home_assistant, mock_service


class TestServiceHelpers(unittest.TestCase):
    """
    Tests the Home Assistant service helpers.
    """

    def setUp(self):     # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.hass = get_test_home_assistant()
        self.calls = mock_service(self.hass, 'test_domain', 'test_service')

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_split_entity_string(self):
        service.call_from_config(self.hass, {
            'service': 'test_domain.test_service',
            'entity_id': 'hello.world, sensor.beer'
        })
        self.hass.pool.block_till_done()
        self.assertEqual(['hello.world', 'sensor.beer'],
                         self.calls[-1].data.get('entity_id'))

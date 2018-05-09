"""The tests for the EDF Teleinfo platform."""

import json
import sys
import unittest
from unittest import mock

from homeassistant.components.sensor import teleinfo
from homeassistant.setup import setup_component

from tests.common import (get_test_home_assistant, load_fixture)


VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'teleinfo',
        'device': '/dev/ttyACM0',
    }
}

VALID_CONFIG_NAME = {
    'sensor': {
        'platform': 'teleinfo',
        'name': 'edf',
        'device': '/dev/ttyACM0',
    }
}


def mock_imports():
    """Mock import of Kylin library."""
    sys.modules['kylin'] = mock.MagicMock()
    sys.modules['kylin.Kylin'] = mock.MagicMock()
    sys.modules['kylin.exceptions.KylinNotFoundError'] = \
        mock.MagicMock()
    sys.modules['kylin.exceptions.KylinSerialError'] = \
        mock.MagicMock()
    sys.modules['kylin.exceptions.KylinError'] = \
        mock.MagicMock()
    import kylin
    kylin.Kylin = KylinMock
    kylin.exceptions.KylinNotFoundError = KylinNotFoundErrorMock
    kylin.exceptions.KylinSerialError = KylinSerialErrorMock
    kylin.exceptions.KylinError = KylinErrorMock


class KylinErrorMock(Exception):
    """Fake Kylin Error."""


class KylinSerialErrorMock(Exception):
    """Fake KylinSerialError."""


class KylinNotFoundErrorMock(Exception):
    """Fake KylinNotFoundError."""


class KylinMock(object):
    """Mock class for the kylin.Kylin object."""

    def __init__(self, port, timeout=0):
        """Initialize Kylin bject."""
        self.port = port
        self.timeout = timeout
        self.sample_data = bytes(load_fixture('teleinfo.txt'), 'ascii')

    def open(self):
        """Open serial connection."""
        pass

    def close(self):
        """Close serial connection."""
        pass

    def readframe(self):
        """Return sample values."""
        content = json.loads(self.sample_data.decode('ascii'))
        print("Frame: %s", content)
        return content

    def exceptions(self):
        """Raise exception."""
        return Exception()


class TestTeleinfoSensor(unittest.TestCase):
    """Test the teleinfo sensor."""

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG_NAME

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def _check_teleinfo_values(self, state):
        self.assertEqual(state.state, '0501340443287')
        self.assertEqual(state.attributes.get('HCHC'), 28005279)
        self.assertEqual(state.attributes.get('HCHP'), 50392600)
        self.assertEqual(state.attributes.get('OPTARIF'), 'HC..')
        self.assertEqual(state.attributes.get('ISOUSC'), 30)
        self.assertEqual(state.attributes.get('IINST'), 1)
        self.assertEqual(state.attributes.get('IMAX'), 32)
        self.assertEqual(state.attributes.get('PAPP'), 330)

    def test_teleinfo_with_minimal_configuration(self):
        """Test Teleinfo with minimal configuration."""
        mock_imports()
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)
        state = self.hass.states.get('sensor.teleinfo')
        self.assertEqual(teleinfo.DEFAULT_NAME, state.name)
        self._check_teleinfo_values(state)

    def test_teleinfo_one_device(self):
        """Test Teleinfo with one device configuration."""
        mock_imports()
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_NAME)
        state = self.hass.states.get('sensor.edf')
        self.assertEqual("edf", state.name)
        self._check_teleinfo_values(state)

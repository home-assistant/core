"""The tests for the Homematic Signal Generator notification platform."""

import unittest

from homeassistant.setup import setup_component
import homeassistant.components.notify as notify
from tests.common import assert_setup_component, get_test_home_assistant


class TestHomematicSignalGen(unittest.TestCase):
    """Test the homematic_signalgen notifications."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_full(self):
        """Test valid configuration"""
        setup_component(self.hass, 'homematic', {
            'homematic': {
                'hosts': {
                    'ccu2': {
                        'host': '127.0.0.1'
                    }
                }
            }
        })
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, 'notify', {
                'notify': {
                    'name': 'test',
                    'platform': 'homematic_signalgen',
                    'address': 'NEQXXXXXXX',
                    'value': '1,1,108000,2'}
            })
        assert handle_config[notify.DOMAIN]

    def test_setup_without_optional(self):
        """Test valid configuration"""
        setup_component(self.hass, 'homematic', {
            'homematic': {
                'hosts': {
                    'ccu2': {
                        'host': '127.0.0.1'
                    }
                }
            }
        })
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, 'notify', {
                'notify': {
                    'name': 'test',
                    'platform': 'homematic_signalgen',
                    'address': 'NEQXXXXXXX'}
            })
        assert handle_config[notify.DOMAIN]

    def test_bad_config(self):
        """Test invalid configuration"""
        config = {
            notify.DOMAIN: {
                'name': 'test',
                'platform': 'homematic_signalgen',
            }
        }
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert not handle_config[notify.DOMAIN]

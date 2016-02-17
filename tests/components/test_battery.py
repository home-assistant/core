"""
tests.components.battery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests battery component.
"""

import os
from datetime import timedelta
import homeassistant.components.device_tracker as device_tracker
from tests.common import get_test_home_assistant


class TestBattery:
    """ Test the Battery component. """

    def setup_method(self, method):
        """ setup tests """
        self.hass = get_test_home_assistant()

        self.yaml_devices = self.hass.config.path(device_tracker.YAML_DEVICES)

        dev_id = 'test1'
        friendly_name = 'test1'
        picture = 'http://placehold.it/200x200'

        device = device_tracker.Device(
            self.hass,
            timedelta(seconds=180),
            0,
            True,
            dev_id,
            None,
            friendly_name,
            picture,
            away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        self.hass.states.set(
            'device_tracker.test1', 'not_home',
            {
                'friendly_name': 'test1',
                'battery': 50
            })

        dev_id = 'test2'
        friendly_name = 'test2'
        picture = 'http://placehold.it/200x200'

        device = device_tracker.Device(
            self.hass, timedelta(seconds=180), 0, True, dev_id, None,
            friendly_name, picture, away_hide=True)
        device_tracker.update_config(self.yaml_devices, dev_id, device)

        self.hass.states.set(
            'device_tracker.test2', 'not_home',
            {
                'friendly_name': 'test2',
                'battery': 50
            })

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def test_battery(self):
        """ Test the Proximity component setup """
        assert battery.setup(self.hass, {
            'battery': {
                'devices': {
                    'test1',
                    'test2'
                }
            }
        })

        state = self.hass.states.get('battery.test1')
        assert state.state == 50
        assert state.attributes.get('status') == 'unknown'

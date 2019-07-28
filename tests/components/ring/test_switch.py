"""The tests for the Ring sensor platform."""
import os
import unittest
import requests_mock
import asynctest
from datetime import datetime


import homeassistant.components.ring.switch as ring
from homeassistant.components import ring as base_ring

from tests.components.ring.test_init import VALID_CONFIG
from tests.common import (
    get_test_config_dir, get_test_home_assistant, load_fixture)


class TestRingSensorSetup(unittest.TestCase):
    """Test the Ring platform."""

    DEVICES = []

    def add_entities(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def cleanup(self):
        """Cleanup any data created from the tests."""
        if os.path.isfile(self.cache):
            os.remove(self.cache)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.cache = get_test_config_dir(base_ring.DEFAULT_CACHEDB)
        self.config = {
            'username': 'foo',
            'password': 'bar',
        }

    def async_schedule_update_ha_state(self, callUpdate):
        """Test creating a task"""

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()
        self.cleanup()

    @requests_mock.Mocker()
    def test_switches_correctly_setup(self, mock):
        """Test the Ring sensor class and methods."""
        mock.post('https://oauth.ring.com/oauth/token',
                  text=load_fixture('ring_oauth.json'))
        mock.post('https://api.ring.com/clients_api/session',
                  text=load_fixture('ring_session.json'))
        mock.get('https://api.ring.com/clients_api/ring_devices',
                 text=load_fixture('ring_devices.json'))
        mock.get('https://api.ring.com/clients_api/doorbots/987652/history',
                 text=load_fixture('ring_doorbots.json'))
        mock.get('https://api.ring.com/clients_api/doorbots/987652/health',
                 text=load_fixture('ring_doorboot_health_attrs.json'))
        mock.get('https://api.ring.com/clients_api/chimes/999999/health',
                 text=load_fixture('ring_chime_health_attrs.json'))

        base_ring.setup(self.hass, VALID_CONFIG)
        ring.setup_platform(self.hass,
                            self.config,
                            self.add_entities,
                            None)

        for device in self.DEVICES:
            device.update()
            if device.name == 'Front siren':
                assert not device.is_on
            elif device.name == 'Internal siren':
                assert device.is_on
            assert device.unique_id == 'aacdef123-siren'
            assert not device.should_poll

    @requests_mock.Mocker()
    @asynctest.mock.patch('homeassistant.components.ring.switch.SirenSwitch.async_schedule_update_ha_state')
    def test_switches_correctly_turn_on(self, mock, mockScheduleUpdate):
        """Test the Ring sensor class and methods."""
        mock.post('https://oauth.ring.com/oauth/token',
                  text=load_fixture('ring_oauth.json'))
        mock.post('https://api.ring.com/clients_api/session',
                  text=load_fixture('ring_session.json'))
        mock.get('https://api.ring.com/clients_api/ring_devices',
                 text=load_fixture('ring_devices.json'))
        mock.get('https://api.ring.com/clients_api/doorbots/987652/history',
                 text=load_fixture('ring_doorbots.json'))
        mock.get('https://api.ring.com/clients_api/doorbots/987652/health',
                 text=load_fixture('ring_doorboot_health_attrs.json'))
        mock.get('https://api.ring.com/clients_api/chimes/999999/health',
                 text=load_fixture('ring_chime_health_attrs.json'))
        mock.put('https://api.ring.com/clients_api/doorbots/987652/siren_on?api_version=9&auth_token=None&duration=1',
                  text=load_fixture('ring_doorbot_siren_on_response.json'))

        base_ring.setup(self.hass, VALID_CONFIG)
        ring.setup_platform(self.hass,
                            self.config,
                            self.add_entities,
                            None)

        first_device = self.DEVICES[0]
        assert not first_device.is_on
        first_device.turn_on()
        assert first_device.is_on
        # Even though the api mock returns that the siren isn't on, calling update
        # shouldn't update the state as we have a timer in place to prevent it.
        first_device.update()
        assert first_device.is_on
        mockScheduleUpdate.assert_called()
        # Set the timer to force the update to take place, turning the switch off
        first_device._no_updates_until = datetime.now()
        first_device.update()
        assert not first_device.is_on

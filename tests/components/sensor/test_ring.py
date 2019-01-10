"""The tests for the Ring sensor platform."""
import os
import unittest
import requests_mock

from homeassistant.components.sensor import ring
from homeassistant.components import ring as base_ring

from tests.components.test_ring import ATTRIBUTION, VALID_CONFIG
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
            'monitored_conditions': [
                'battery',
                'last_activity',
                'last_ding',
                'last_motion',
                'volume',
                'wifi_signal_category',
                'wifi_signal_strength']
        }

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()
        self.cleanup()

    @requests_mock.Mocker()
    def test_sensor(self, mock):
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
            if device.name == 'Front Battery':
                assert 80 == device.state
                assert 'hp_cam_v1' == \
                    device.device_state_attributes['kind']
                assert 'stickup_cams' == \
                    device.device_state_attributes['type']
            if device.name == 'Front Door Battery':
                assert 100 == device.state
                assert 'lpd_v1' == \
                    device.device_state_attributes['kind']
                assert 'chimes' != \
                       device.device_state_attributes['type']
            if device.name == 'Downstairs Volume':
                assert 2 == device.state
                assert '1.2.3' == \
                    device.device_state_attributes['firmware']
                assert 'ring_mock_wifi' == \
                    device.device_state_attributes['wifi_name']
                assert 'mdi:bell-ring' == device.icon
                assert 'chimes' == \
                    device.device_state_attributes['type']
            if device.name == 'Front Door Last Activity':
                assert not device.device_state_attributes['answered']
                assert 'America/New_York' == \
                    device.device_state_attributes['timezone']

            if device.name == 'Downstairs WiFi Signal Strength':
                assert -39 == device.state

            if device.name == 'Front Door WiFi Signal Category':
                assert 'good' == device.state

            if device.name == 'Front Door WiFi Signal Strength':
                assert -58 == device.state

            assert device.entity_picture is None
            assert ATTRIBUTION == \
                device.device_state_attributes['attribution']

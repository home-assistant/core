"""The tests for the demo platform."""
import unittest

from homeassistant.components import geo_location
from homeassistant.components.geo_location.demo import DemoManager, \
    NUMBER_OF_DEMO_DEVICES, setup_platform
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component

CONFIG = {
    geo_location.DOMAIN: [
        {
            'platform': 'demo'
        }
    ]
}


class TestDemoPlatform(unittest.TestCase):
    """Test the demo platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_via_config(self):
        """Test setup of demo platform via configuration."""
        with assert_setup_component(0, 'geo_location'):
            self.assertTrue(setup_component(self.hass, 'demo',
                                            CONFIG))

    def test_setup_platform(self):
        """Test setup of demo platform."""
        devices = []

        @callback
        def add_devices_callback(events):
            """Add recorded devices."""
            devices.extend(events)

        self.assertTrue(setup_platform(self.hass, None, add_devices_callback,
                                       None))
        assert len(devices) == NUMBER_OF_DEMO_DEVICES

    def setup_manager(self):
        """Setup demo manager."""
        devices = []

        @callback
        def add_devices_callback(events):
            """Add recorded devices."""
            devices.extend(events)

        return DemoManager(self.hass, add_devices_callback)

    def test_demo_manager(self):
        """Test demo manager setup."""
        manager = self.setup_manager()
        devices = manager._managed_devices
        assert len(devices) == NUMBER_OF_DEMO_DEVICES
        # Check a single device's attributes.
        device = devices[0]
        self.assertAlmostEqual(device.distance, device.state, places=0)
        self.assertAlmostEqual(device.latitude, self.hass.config.latitude,
                               delta=1.0)
        self.assertAlmostEqual(device.longitude, self.hass.config.longitude,
                               delta=1.0)
        assert device.icon is None
        assert device.device_state_attributes == {
            ATTR_LATITUDE: device.latitude, ATTR_LONGITUDE: device.longitude}

    def test_demo_manager_update(self):
        """Test demo manager setup with update."""
        manager = self.setup_manager()
        devices1 = manager._managed_devices.copy()
        self.assertEqual(NUMBER_OF_DEMO_DEVICES, len(devices1))
        # Update (replaces 1 device).
        manager._update()
        devices2 = manager._managed_devices.copy()
        self.assertEqual(NUMBER_OF_DEMO_DEVICES, len(devices2))
        self.assertNotEqual(devices1, devices2)

    def test_group_order(self):
        """Test order of entries in group."""
        manager = self.setup_manager()
        devices = manager._managed_devices.copy()
        group = manager.group
        last_distance = 0.0
        for entity_id in group.state_attributes.get(ATTR_ENTITY_ID):
            device = next((device for device in devices if device.entity_id
                           == entity_id), None)
            self.assertIsNotNone(device)
            assert device.distance >= last_distance
            last_distance = device.distance

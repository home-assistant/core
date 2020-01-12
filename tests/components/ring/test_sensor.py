"""The tests for the Ring sensor platform."""
from asyncio import run_coroutine_threadsafe
import unittest
from unittest.mock import patch

import requests_mock

from homeassistant.components import ring as base_ring
import homeassistant.components.ring.sensor as ring
from homeassistant.helpers.icon import icon_for_battery_level

from tests.common import get_test_home_assistant, load_fixture, mock_storage
from tests.components.ring.test_init import ATTRIBUTION, VALID_CONFIG


class TestRingSensorSetup(unittest.TestCase):
    """Test the Ring platform."""

    DEVICES = []

    def add_entities(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = {
            "username": "foo",
            "password": "bar",
            "monitored_conditions": [
                "battery",
                "last_activity",
                "last_ding",
                "last_motion",
                "volume",
                "wifi_signal_category",
                "wifi_signal_strength",
            ],
        }

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_sensor(self, mock):
        """Test the Ring sensor class and methods."""
        mock.post(
            "https://oauth.ring.com/oauth/token", text=load_fixture("ring_oauth.json")
        )
        mock.post(
            "https://api.ring.com/clients_api/session",
            text=load_fixture("ring_session.json"),
        )
        mock.get(
            "https://api.ring.com/clients_api/ring_devices",
            text=load_fixture("ring_devices.json"),
        )
        mock.get(
            "https://api.ring.com/clients_api/doorbots/987652/history",
            text=load_fixture("ring_doorbots.json"),
        )
        mock.get(
            "https://api.ring.com/clients_api/doorbots/987652/health",
            text=load_fixture("ring_doorboot_health_attrs.json"),
        )
        mock.get(
            "https://api.ring.com/clients_api/chimes/999999/health",
            text=load_fixture("ring_chime_health_attrs.json"),
        )

        with mock_storage(), patch("homeassistant.components.ring.PLATFORMS", []):
            run_coroutine_threadsafe(
                base_ring.async_setup(self.hass, VALID_CONFIG), self.hass.loop
            ).result()
            run_coroutine_threadsafe(
                self.hass.async_block_till_done(), self.hass.loop
            ).result()
            run_coroutine_threadsafe(
                ring.async_setup_entry(self.hass, None, self.add_entities),
                self.hass.loop,
            ).result()

        for device in self.DEVICES:
            # Mimick add to hass
            device.hass = self.hass
            run_coroutine_threadsafe(
                device.async_added_to_hass(), self.hass.loop,
            ).result()

            # Entity update data from ring data
            device.update()
            if device.name == "Front Battery":
                expected_icon = icon_for_battery_level(
                    battery_level=int(device.state), charging=False
                )
                assert device.icon == expected_icon
                assert 80 == device.state
            if device.name == "Front Door Battery":
                assert 100 == device.state
            if device.name == "Downstairs Volume":
                assert 2 == device.state
                assert "ring_mock_wifi" == device.device_state_attributes["wifi_name"]
                assert "mdi:bell-ring" == device.icon
            if device.name == "Front Door Last Activity":
                assert not device.device_state_attributes["answered"]
                assert "America/New_York" == device.device_state_attributes["timezone"]

            if device.name == "Downstairs WiFi Signal Strength":
                assert -39 == device.state

            if device.name == "Front Door WiFi Signal Category":
                assert "good" == device.state

            if device.name == "Front Door WiFi Signal Strength":
                assert -58 == device.state

            assert device.entity_picture is None
            assert ATTRIBUTION == device.device_state_attributes["attribution"]
            assert not device.should_poll

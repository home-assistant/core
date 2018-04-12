"""Test HomeKit util module."""
import unittest

import voluptuous as vol
import pytest

from homeassistant.core import callback
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import HOMEKIT_NOTIFY_ID
from homeassistant.components.homekit.util import (
    show_setup_message, dismiss_setup_message, convert_to_float,
    temperature_to_homekit, temperature_to_states, ATTR_CODE,
    density_to_air_quality)
from homeassistant.components.homekit.util import validate_entity_config \
    as vec
from homeassistant.components.persistent_notification import (
    SERVICE_CREATE, SERVICE_DISMISS, ATTR_NOTIFICATION_ID)
from homeassistant.const import (
    EVENT_CALL_SERVICE, ATTR_DOMAIN, ATTR_SERVICE, ATTR_SERVICE_DATA,
    TEMP_CELSIUS, TEMP_FAHRENHEIT, STATE_UNKNOWN)

from tests.common import get_test_home_assistant


def test_validate_entity_config():
    """Test validate entities."""
    configs = [{'invalid_entity_id': {}}, {'demo.test': 1},
               {'demo.test': 'test'}, {'demo.test': [1, 2]},
               {'demo.test': None}]

    for conf in configs:
        with pytest.raises(vol.Invalid):
            vec(conf)

    assert vec({}) == {}
    assert vec({'alarm_control_panel.demo': {ATTR_CODE: '1234'}}) == \
        {'alarm_control_panel.demo': {ATTR_CODE: '1234'}}


def test_convert_to_float():
    """Test convert_to_float method."""
    assert convert_to_float(12) == 12
    assert convert_to_float(12.4) == 12.4
    assert convert_to_float(STATE_UNKNOWN) is None
    assert convert_to_float(None) is None


def test_temperature_to_homekit():
    """Test temperature conversion from HA to HomeKit."""
    assert temperature_to_homekit(20.46, TEMP_CELSIUS) == 20.5
    assert temperature_to_homekit(92.1, TEMP_FAHRENHEIT) == 33.4


def test_temperature_to_states():
    """Test temperature conversion from HomeKit to HA."""
    assert temperature_to_states(20, TEMP_CELSIUS) == 20.0
    assert temperature_to_states(20.2, TEMP_FAHRENHEIT) == 68.4


def test_density_to_air_quality():
    """Test map PM2.5 density to HomeKit AirQuality level."""
    assert density_to_air_quality(0) == 1
    assert density_to_air_quality(35) == 1
    assert density_to_air_quality(35.1) == 2
    assert density_to_air_quality(75) == 2
    assert density_to_air_quality(115) == 3
    assert density_to_air_quality(150) == 4
    assert density_to_air_quality(300) == 5


class TestUtil(unittest.TestCase):
    """Test all HomeKit util methods."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.events = []

        @callback
        def record_event(event):
            """Track called event."""
            self.events.append(event)

        self.hass.bus.listen(EVENT_CALL_SERVICE, record_event)

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_show_setup_msg(self):
        """Test show setup message as persistence notification."""
        bridge = HomeBridge(self.hass)

        show_setup_message(self.hass, bridge)
        self.hass.block_till_done()

        data = self.events[0].data
        self.assertEqual(
            data.get(ATTR_DOMAIN, None), 'persistent_notification')
        self.assertEqual(data.get(ATTR_SERVICE, None), SERVICE_CREATE)
        self.assertNotEqual(data.get(ATTR_SERVICE_DATA, None), None)
        self.assertEqual(
            data[ATTR_SERVICE_DATA].get(ATTR_NOTIFICATION_ID, None),
            HOMEKIT_NOTIFY_ID)

    def test_dismiss_setup_msg(self):
        """Test dismiss setup message."""
        dismiss_setup_message(self.hass)
        self.hass.block_till_done()

        data = self.events[0].data
        self.assertEqual(
            data.get(ATTR_DOMAIN, None), 'persistent_notification')
        self.assertEqual(data.get(ATTR_SERVICE, None), SERVICE_DISMISS)
        self.assertNotEqual(data.get(ATTR_SERVICE_DATA, None), None)
        self.assertEqual(
            data[ATTR_SERVICE_DATA].get(ATTR_NOTIFICATION_ID, None),
            HOMEKIT_NOTIFY_ID)

"""Tests for the luxtronik binary sensor component."""

import unittest
from unittest.mock import Mock, patch

import homeassistant.components.luxtronik as luxtronik
from homeassistant.components.luxtronik import DOMAIN
import homeassistant.components.luxtronik.binary_sensor as luxtronik_binary_sensor

from tests.common import get_test_home_assistant


class TestLuxtronikBinarySensor(unittest.TestCase):
    """Test the Luxtronik binary sensor component."""

    DEVICES = []

    def add_entities(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch("homeassistant.components.luxtronik.Lux")
    def test_luxtronik_sensor_minimal(self, mock_luxtronik):
        """Test minimnal sensor setup."""
        self.DEVICES = []
        mock_sensor = Mock()
        mock_sensor.name = "ID_WEB_EVUin"
        mock_sensor.value = True
        mock_luxtronik().calculations.get.return_value = mock_sensor
        luxtronik.setup(
            self.hass, {DOMAIN: {"host": "192.168.1.1", "port": 8889, "safe": True}}
        )
        config = {
            "platform": DOMAIN,
            "sensors": [
                {
                    "group": "calculations",
                    "id": "ID_WEB_EVUin",
                    "friendly_name": None,
                    "icon": None,
                    "invert": False,
                }
            ],
        }
        luxtronik_binary_sensor.setup_platform(
            self.hass, config, self.add_entities, None
        )
        assert self.DEVICES[0].entity_id == "luxtronik.id_web_evuin"
        assert self.DEVICES[0].name == "ID_WEB_EVUin"
        assert self.DEVICES[0].is_on

    @patch("homeassistant.components.luxtronik.Lux")
    def test_luxtronik_sensor_invert(self, mock_luxtronik):
        """Test inverted sensor setup."""
        self.DEVICES = []
        mock_sensor = Mock()
        mock_sensor.name = "ID_WEB_EVUin"
        mock_sensor.value = True
        mock_luxtronik().calculations.get.return_value = mock_sensor
        luxtronik.setup(
            self.hass, {DOMAIN: {"host": "192.168.1.1", "port": 8889, "safe": True}}
        )
        config = {
            "platform": DOMAIN,
            "sensors": [
                {
                    "group": "calculations",
                    "id": "ID_WEB_EVUin",
                    "friendly_name": None,
                    "icon": None,
                    "invert": True,
                }
            ],
        }
        luxtronik_binary_sensor.setup_platform(
            self.hass, config, self.add_entities, None
        )
        assert not self.DEVICES[0].is_on

    @patch("homeassistant.components.luxtronik.Lux")
    def test_luxtronik_sensor_full(self, mock_luxtronik):
        """Test full sensor setup."""
        self.DEVICES = []
        mock_sensor = Mock()
        mock_sensor.name = "ID_WEB_EVUin"
        mock_sensor.value = True
        mock_luxtronik().calculations.get.return_value = mock_sensor
        luxtronik.setup(
            self.hass, {DOMAIN: {"host": "192.168.1.1", "port": 8889, "safe": True}}
        )
        config = {
            "platform": DOMAIN,
            "sensors": [
                {
                    "group": "calculations",
                    "id": "ID_WEB_EVUin",
                    "friendly_name": "Utility Company Lock",
                    "icon": "mdi:flash",
                    "invert": False,
                }
            ],
        }
        luxtronik_binary_sensor.setup_platform(
            self.hass, config, self.add_entities, None
        )
        assert self.DEVICES[0].entity_id == "luxtronik.utility_company_lock"
        assert self.DEVICES[0].name == "Utility Company Lock"
        assert self.DEVICES[0].icon == "mdi:flash"
        assert self.DEVICES[0].is_on

    @patch("homeassistant.components.luxtronik.Lux")
    def test_luxtronik_sensor_multiple(self, mock_luxtronik):
        """Test multiple sensor setup."""
        self.DEVICES = []
        mock_calc_sensor = Mock()
        mock_luxtronik().calculations.get.return_value = mock_calc_sensor
        mock_param_sensor = Mock()
        mock_luxtronik().parameters.get.return_value = mock_param_sensor
        mock_visi_sensor = Mock()
        mock_luxtronik().visibilities.get.return_value = mock_visi_sensor
        luxtronik.setup(
            self.hass, {DOMAIN: {"host": "192.168.1.1", "port": 8889, "safe": True}}
        )
        config = {
            "platform": DOMAIN,
            "sensors": [
                {
                    "group": "calculations",
                    "id": "ID_WEB_EVUin",
                    "friendly_name": None,
                    "icon": None,
                    "invert": False,
                },
                {
                    "group": "parameters",
                    "id": "ID_Einst_isTwin",
                    "friendly_name": None,
                    "icon": None,
                    "invert": False,
                },
                {
                    "group": "visibilities",
                    "id": "ID_Visi_IN_EVU",
                    "friendly_name": None,
                    "icon": None,
                    "invert": False,
                },
            ],
        }
        luxtronik_binary_sensor.setup_platform(
            self.hass, config, self.add_entities, None
        )
        assert len(self.DEVICES) == 3

    @patch("homeassistant.components.luxtronik.sensor._LOGGER")
    @patch("homeassistant.components.luxtronik.Lux")
    def test_luxtronik_invalid_sensor(self, mock_luxtronik, mock_logger):
        """Test invalid sensor setup."""
        self.DEVICES = []
        mock_luxtronik().calculations.get.return_value = None
        luxtronik.setup(
            self.hass, {DOMAIN: {"host": "192.168.1.1", "port": 8889, "safe": True}}
        )
        config = {
            "platform": DOMAIN,
            "sensors": [
                {
                    "group": "calculations",
                    "id": "ID_INVALID",
                    "friendly_name": None,
                    "icon": None,
                    "invert": False,
                }
            ],
        }
        luxtronik_binary_sensor.setup_platform(
            self.hass, config, self.add_entities, None
        )
        assert not self.DEVICES
        assert mock_logger.warning.called_with(
            "Invalid Luxtronik ID ID_INVALID in group calculations"
        )

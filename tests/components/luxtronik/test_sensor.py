"""Tests for the luxtronik sensor component."""

import unittest
from unittest.mock import Mock, patch

import homeassistant.components.luxtronik as luxtronik
from homeassistant.components.luxtronik import DOMAIN
import homeassistant.components.luxtronik.sensor as luxtronik_sensor

from tests.common import get_test_home_assistant


class TestLuxtronikSensor(unittest.TestCase):
    """Test the Luxtronik sensor component."""

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
        mock_sensor.name = "ID_WEB_Temperatur_TVL"
        mock_sensor.measurement_type = "celsius"
        mock_sensor.value = 21.2
        mock_luxtronik().calculations.get.return_value = mock_sensor
        luxtronik.setup(
            self.hass, {DOMAIN: {"host": "192.168.1.1", "port": 8889, "safe": True}}
        )
        config = {
            "platform": DOMAIN,
            "sensors": [
                {
                    "group": "calculations",
                    "id": "ID_WEB_Temperatur_TVL",
                    "friendly_name": None,
                    "icon": None,
                }
            ],
        }
        luxtronik_sensor.setup_platform(self.hass, config, self.add_entities, None)
        assert self.DEVICES[0].entity_id == "luxtronik.id_web_temperatur_tvl"
        assert self.DEVICES[0].name == "ID_WEB_Temperatur_TVL"
        assert self.DEVICES[0].unit_of_measurement == "°C"
        assert self.DEVICES[0].icon == "mdi:thermometer"
        assert self.DEVICES[0].state == 21.2

    @patch("homeassistant.components.luxtronik.Lux")
    def test_luxtronik_sensor_full(self, mock_luxtronik):
        """Test full sensor setup."""
        self.DEVICES = []
        mock_sensor = Mock()
        mock_sensor.name = "ID_WEB_Temperatur_TVL"
        mock_sensor.measurement_type = "celsius"
        mock_sensor.value = 23.2
        mock_luxtronik().calculations.get.return_value = mock_sensor
        luxtronik.setup(
            self.hass, {DOMAIN: {"host": "192.168.1.1", "port": 8889, "safe": True}}
        )
        config = {
            "platform": DOMAIN,
            "sensors": [
                {
                    "group": "calculations",
                    "id": "ID_WEB_Temperatur_TVL",
                    "friendly_name": "Temperature heating flow",
                    "icon": "mdi:flash",
                }
            ],
        }
        luxtronik_sensor.setup_platform(self.hass, config, self.add_entities, None)
        assert self.DEVICES[0].entity_id == "luxtronik.temperature_heating_flow"
        assert self.DEVICES[0].name == "Temperature heating flow"
        assert self.DEVICES[0].unit_of_measurement == "°C"
        assert self.DEVICES[0].icon == "mdi:flash"
        assert self.DEVICES[0].state == 23.2

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
                    "id": "ID_WEB_Temperatur_TVL",
                    "friendly_name": None,
                    "icon": None,
                },
                {
                    "group": "parameters",
                    "id": "ID_Ba_Hz_akt",
                    "friendly_name": None,
                    "icon": None,
                },
                {
                    "group": "visibilities",
                    "id": "ID_Visi_Heizung",
                    "friendly_name": None,
                    "icon": None,
                },
            ],
        }
        luxtronik_sensor.setup_platform(self.hass, config, self.add_entities, None)
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
                }
            ],
        }
        luxtronik_sensor.setup_platform(self.hass, config, self.add_entities, None)
        assert not self.DEVICES
        assert mock_logger.warning.called_with(
            "Invalid Luxtronik ID ID_INVALID in group calculations"
        )

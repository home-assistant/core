"""Tests for MH-Z19 sensor."""
import unittest
from unittest.mock import DEFAULT, Mock, patch

import homeassistant.components.mhz19.sensor as mhz19
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION, TEMP_FAHRENHEIT
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant


class TestMHZ19Sensor(unittest.TestCase):
    """Test the MH-Z19 sensor."""

    hass = None

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_missing_config(self):
        """Test setup with configuration missing required entries."""
        with assert_setup_component(0):
            assert setup_component(self.hass, DOMAIN, {"sensor": {"platform": "mhz19"}})

    @patch("pmsensor.co2sensor.read_mh_z19", side_effect=OSError("test error"))
    def test_setup_failed_connect(self, mock_co2):
        """Test setup when connection error occurs."""
        assert not mhz19.setup_platform(
            self.hass,
            {"platform": "mhz19", mhz19.CONF_SERIAL_DEVICE: "test.serial"},
            None,
        )

    def test_setup_connected(self):
        """Test setup when connection succeeds."""
        with patch.multiple(
            "pmsensor.co2sensor",
            read_mh_z19=DEFAULT,
            read_mh_z19_with_temperature=DEFAULT,
        ):
            from pmsensor.co2sensor import read_mh_z19_with_temperature

            read_mh_z19_with_temperature.return_value = None
            mock_add = Mock()
            assert mhz19.setup_platform(
                self.hass,
                {
                    "platform": "mhz19",
                    "monitored_conditions": ["co2", "temperature"],
                    mhz19.CONF_SERIAL_DEVICE: "test.serial",
                },
                mock_add,
            )
        assert mock_add.call_count == 1

    @patch(
        "pmsensor.co2sensor.read_mh_z19_with_temperature",
        side_effect=OSError("test error"),
    )
    def aiohttp_client_update_oserror(self, mock_function):
        """Test MHZClient when library throws OSError."""
        from pmsensor import co2sensor

        client = mhz19.MHZClient(co2sensor, "test.serial")
        client.update()
        assert {} == client.data

    @patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(5001, 24))
    def aiohttp_client_update_ppm_overflow(self, mock_function):
        """Test MHZClient when ppm is too high."""
        from pmsensor import co2sensor

        client = mhz19.MHZClient(co2sensor, "test.serial")
        client.update()
        assert client.data.get("co2") is None

    @patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(1000, 24))
    def aiohttp_client_update_good_read(self, mock_function):
        """Test MHZClient when ppm is too high."""
        from pmsensor import co2sensor

        client = mhz19.MHZClient(co2sensor, "test.serial")
        client.update()
        assert {"temperature": 24, "co2": 1000} == client.data

    @patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(1000, 24))
    def test_co2_sensor(self, mock_function):
        """Test CO2 sensor."""
        from pmsensor import co2sensor

        client = mhz19.MHZClient(co2sensor, "test.serial")
        sensor = mhz19.MHZ19Sensor(client, mhz19.SENSOR_CO2, None, "name")
        sensor.update()

        assert sensor.name == "name: CO2"
        assert sensor.state == 1000
        assert sensor.unit_of_measurement == CONCENTRATION_PARTS_PER_MILLION
        assert sensor.should_poll
        assert sensor.device_state_attributes == {"temperature": 24}

    @patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(1000, 24))
    def test_temperature_sensor(self, mock_function):
        """Test temperature sensor."""
        from pmsensor import co2sensor

        client = mhz19.MHZClient(co2sensor, "test.serial")
        sensor = mhz19.MHZ19Sensor(client, mhz19.SENSOR_TEMPERATURE, None, "name")
        sensor.update()

        assert sensor.name == "name: Temperature"
        assert sensor.state == 24
        assert sensor.unit_of_measurement == "°C"
        assert sensor.should_poll
        assert sensor.device_state_attributes == {"co2_concentration": 1000}

    @patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(1000, 24))
    def test_temperature_sensor_f(self, mock_function):
        """Test temperature sensor."""
        from pmsensor import co2sensor

        client = mhz19.MHZClient(co2sensor, "test.serial")
        sensor = mhz19.MHZ19Sensor(
            client, mhz19.SENSOR_TEMPERATURE, TEMP_FAHRENHEIT, "name"
        )
        sensor.update()

        assert sensor.state == 75.2

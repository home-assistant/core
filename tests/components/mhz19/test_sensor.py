"""Tests for MH-Z19 sensor."""
from unittest.mock import DEFAULT, Mock, patch

from pmsensor import co2sensor
from pmsensor.co2sensor import read_mh_z19_with_temperature

import homeassistant.components.mhz19.sensor as mhz19
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


async def test_setup_missing_config(hass):
    """Test setup with configuration missing required entries."""
    with assert_setup_component(0):
        assert await async_setup_component(
            hass, DOMAIN, {"sensor": {"platform": "mhz19"}}
        )


@patch("pmsensor.co2sensor.read_mh_z19", side_effect=OSError("test error"))
async def test_setup_failed_connect(mock_co2, hass):
    """Test setup when connection error occurs."""
    assert not mhz19.setup_platform(
        hass,
        {"platform": "mhz19", mhz19.CONF_SERIAL_DEVICE: "test.serial"},
        None,
    )


async def test_setup_connected(hass):
    """Test setup when connection succeeds."""
    with patch.multiple(
        "pmsensor.co2sensor",
        read_mh_z19=DEFAULT,
        read_mh_z19_with_temperature=DEFAULT,
    ):
        read_mh_z19_with_temperature.return_value = None
        mock_add = Mock()
        assert mhz19.setup_platform(
            hass,
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
async def aiohttp_client_update_oserror(mock_function):
    """Test MHZClient when library throws OSError."""
    client = mhz19.MHZClient(co2sensor, "test.serial")
    client.update()
    assert {} == client.data


@patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(5001, 24))
async def aiohttp_client_update_ppm_overflow(mock_function):
    """Test MHZClient when ppm is too high."""
    client = mhz19.MHZClient(co2sensor, "test.serial")
    client.update()
    assert client.data.get("co2") is None


@patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(1000, 24))
async def aiohttp_client_update_good_read(mock_function):
    """Test MHZClient when ppm is too high."""
    client = mhz19.MHZClient(co2sensor, "test.serial")
    client.update()
    assert {"temperature": 24, "co2": 1000} == client.data


@patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(1000, 24))
async def test_co2_sensor(mock_function):
    """Test CO2 sensor."""
    client = mhz19.MHZClient(co2sensor, "test.serial")
    sensor = mhz19.MHZ19Sensor(client, mhz19.SENSOR_CO2, None, "name")
    sensor.update()

    assert sensor.name == "name: CO2"
    assert sensor.state == 1000
    assert sensor.unit_of_measurement == CONCENTRATION_PARTS_PER_MILLION
    assert sensor.should_poll
    assert sensor.extra_state_attributes == {"temperature": 24}


@patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(1000, 24))
async def test_temperature_sensor(mock_function):
    """Test temperature sensor."""
    client = mhz19.MHZClient(co2sensor, "test.serial")
    sensor = mhz19.MHZ19Sensor(client, mhz19.SENSOR_TEMPERATURE, None, "name")
    sensor.update()

    assert sensor.name == "name: Temperature"
    assert sensor.state == 24
    assert sensor.unit_of_measurement == TEMP_CELSIUS
    assert sensor.should_poll
    assert sensor.extra_state_attributes == {"co2_concentration": 1000}


@patch("pmsensor.co2sensor.read_mh_z19_with_temperature", return_value=(1000, 24))
async def test_temperature_sensor_f(mock_function):
    """Test temperature sensor."""
    client = mhz19.MHZClient(co2sensor, "test.serial")
    sensor = mhz19.MHZ19Sensor(
        client, mhz19.SENSOR_TEMPERATURE, TEMP_FAHRENHEIT, "name"
    )
    sensor.update()

    assert sensor.state == 75.2

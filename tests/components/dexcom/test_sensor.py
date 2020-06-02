"""The sensor tests for the griddy platform."""
from asynctest import patch
from pydexcom import GlucoseReading

from homeassistant.components.dexcom.const import DOMAIN
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component


async def test_sensors(hass):
    """Test we get sensor data."""
    _mock_glucose_reading = GlucoseReading(
        {
            "DT": "/Date(1587165223000+0000)/",
            "ST": "/Date(1587179623000)/",
            "Trend": 4,
            "Value": 110,
            "WT": "/Date(1587179623000)/",
        }
    )
    with patch(
        "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        return_value=_mock_glucose_reading,
    ), patch(
        "homeassistant.components.dexcom.Dexcom.create_session",
        return_value="test_session_id",
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_USERNAME: "test_username",
                    CONF_PASSWORD: "test_password",
                    "server": "US",
                    CONF_UNIT_OF_MEASUREMENT: "mg/dL",
                }
            },
        )
        await hass.async_block_till_done()
    sensor_dexcom_test_username_glucose_value = hass.states.get(
        "sensor.dexcom_test_username_glucose_value"
    )
    assert sensor_dexcom_test_username_glucose_value.state == str(
        _mock_glucose_reading.mg_dl
    )
    sensor_dexcom_test_username_glucose_trend = hass.states.get(
        "sensor.dexcom_test_username_glucose_trend"
    )
    assert (
        sensor_dexcom_test_username_glucose_trend.state
        == _mock_glucose_reading.trend_description
    )


async def test_sensors_unavailable(hass):
    """Test we handle sensor unavailable."""
    _mock_glucose_reading = None
    with patch(
        "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        return_value=_mock_glucose_reading,
    ), patch(
        "homeassistant.components.dexcom.Dexcom.create_session",
        return_value="test_session_id",
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_USERNAME: "test_username",
                    CONF_PASSWORD: "test_password",
                    "server": "US",
                    CONF_UNIT_OF_MEASUREMENT: "mg/dL",
                }
            },
        )
        await hass.async_block_till_done()
    sensor_dexcom_test_username_glucose_value = hass.states.get(
        "sensor.dexcom_test_username_glucose_value"
    )
    assert sensor_dexcom_test_username_glucose_value.state == STATE_UNAVAILABLE
    sensor_dexcom_test_username_glucose_trend = hass.states.get(
        "sensor.dexcom_test_username_glucose_trend"
    )
    assert sensor_dexcom_test_username_glucose_trend.state == STATE_UNAVAILABLE

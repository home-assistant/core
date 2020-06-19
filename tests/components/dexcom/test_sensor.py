"""The sensor tests for the griddy platform."""
from pydexcom import GlucoseReading

from homeassistant.components.dexcom.const import DOMAIN
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


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
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_username",
        unique_id="test_username",
        data={
            CONF_USERNAME: "test_username",
            CONF_PASSWORD: "test_password",
            "server": "US",
            CONF_UNIT_OF_MEASUREMENT: "mg/dL",
        },
    )
    with patch(
        "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        return_value=_mock_glucose_reading,
    ), patch(
        "homeassistant.components.dexcom.Dexcom.create_session",
        return_value="test_session_id",
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    test_username_glucose_value = hass.states.get(
        "sensor.dexcom_test_username_glucose_value"
    )
    assert test_username_glucose_value.state == str(_mock_glucose_reading.mg_dl)
    test_username_glucose_trend = hass.states.get(
        "sensor.dexcom_test_username_glucose_trend"
    )
    assert test_username_glucose_trend.state == _mock_glucose_reading.trend_description


async def test_sensors_unavailable(hass):
    """Test we handle sensor unavailable."""
    _mock_glucose_reading = None
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_username",
        unique_id="test_username",
        data={
            CONF_USERNAME: "test_username",
            CONF_PASSWORD: "test_password",
            "server": "US",
            CONF_UNIT_OF_MEASUREMENT: "mg/dL",
        },
    )
    with patch(
        "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        return_value=_mock_glucose_reading,
    ), patch(
        "homeassistant.components.dexcom.Dexcom.create_session",
        return_value="test_session_id",
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    test_username_glucose_value = hass.states.get(
        "sensor.dexcom_test_username_glucose_value"
    )
    assert test_username_glucose_value.state == STATE_UNAVAILABLE
    test_username_glucose_trend = hass.states.get(
        "sensor.dexcom_test_username_glucose_trend"
    )
    assert test_username_glucose_trend.state == STATE_UNAVAILABLE

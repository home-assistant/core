"""Test sensor of WittIOT integration."""
import json
from unittest.mock import patch

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.wittiot.const import (
    CONF_IP,
    CONNECTION_TYPE,
    DEVICE_NAME,
    DOMAIN,
)
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


async def test_sensors(hass: HomeAssistant) -> None:
    """Test the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="GW2000B-WIFICB44",
        data={
            DEVICE_NAME: "GW2000B-WIFICB44",
            CONF_IP: "1.1.1.1",
            CONNECTION_TYPE: "Local",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "wittiot.API.request_loc_allinfo",
        return_value=json.loads(load_fixture("wittiot/device_data.json")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.gw2000b_wificb44_main_data_indoor_temp")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "°C"
    assert state.attributes.get(ATTR_STATE_CLASS) == "measurement"
    assert state.state == "13.5"

    state = hass.states.get("sensor.gw2000b_wificb44_main_data_outdoor_temp")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "°C"
    assert state.attributes.get(ATTR_STATE_CLASS) == "measurement"
    assert state.state == "26.5"

    state = hass.states.get("sensor.gw2000b_wificb44_main_data_indoor_humidity")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "%"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == "humidity"
    assert state.state == "1"

    state = hass.states.get("sensor.gw2000b_wificb44_main_data_outdoor_humidity")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "%"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == "humidity"
    assert state.state == "53"

    state = hass.states.get("sensor.gw2000b_wificb44_main_data_absolute")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "hPa"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == "pressure"
    assert state.state == "302.07"

    state = hass.states.get("sensor.gw2000b_wificb44_main_data_wind_speed")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "mph"
    assert state.attributes.get(ATTR_STATE_CLASS) == "measurement"
    assert state.state == "0.0"

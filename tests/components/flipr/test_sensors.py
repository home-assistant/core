"""Test the Flipr sensor and binary sensor."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.components.flipr.const import (
    CONF_FLIPR_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

MOCK_DATE_TIME = datetime(2021, 2, 15, 9, 10, 32, tzinfo=dt_util.UTC)

MOCK_FLIPR_MEASURE = {
    "temperature": 10.5,
    "ph": 7.03,
    "chlorine": 0.23654886,
    "red_ox": 657.58,
    "date_time": MOCK_DATE_TIME,
    "ph_status": "TooLow",
    "chlorine_status": "Medium",
}


async def test_sensors(hass: HomeAssistant) -> None:
    """Test the creation and values of the Flipr sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_entry_unique_id",
        data={
            CONF_USERNAME: "toto@toto.com",
            CONF_PASSWORD: "myPassword",
            CONF_FLIPR_ID: "myfliprid",
        },
    )

    entry.add_to_hass(hass)

    registry = await hass.helpers.entity_registry.async_get_registry()

    # Pre-create registry entries for disabled by default sensors
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "cfe92100-67c4-11d4-a45f-f8d027761251_uptime",
        suggested_object_id="sensor.flipr_myfliprid_chlorine",
        disabled_by=None,
    )

    with patch(
        "homeassistant.components.flipr.decrypt_data", return_value="myPassword"
    ), patch(
        "flipr_api.FliprAPIRestClient.get_pool_measure_latest",
        return_value=MOCK_FLIPR_MEASURE,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.flipr_myfliprid_ph")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:pool"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "ph"
    assert state.state == "7.03"

    state = hass.states.get("sensor.flipr_myfliprid_water_temp")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:coolant-temperature"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is TEMP_CELSIUS
    assert state.state == "10.5"

    state = hass.states.get("sensor.flipr_myfliprid_date_measure")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2021-02-15 09:10:32+00:00"

    state = hass.states.get("sensor.flipr_myfliprid_red_ox")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:pool"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "mV"
    assert state.state == "657.58"

    state = hass.states.get("sensor.flipr_myfliprid_chlorine")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:pool"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "mV"
    assert state.state == "0.23654886"

    state = hass.states.get("binary_sensor.flipr_myfliprid_ph_status")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "off"

    state = hass.states.get("binary_sensor.flipr_myfliprid_chlorine_status")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "on"

    entry = registry.async_get("binary_sensor.flipr_myfliprid_chlorine_status")
    assert entry
    assert entry.unique_id == "myfliprid-chlorine_status"

"""Test the Flipr sensor and binary sensor."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.components.flipr.const import CONF_FLIPR_ID, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_EMAIL,
    CONF_PASSWORD,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

# Data for the mocked object returned via flipr_api client.
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
            CONF_EMAIL: "toto@toto.com",
            CONF_PASSWORD: "myPassword",
            CONF_FLIPR_ID: "myfliprid",
        },
    )

    entry.add_to_hass(hass)

    registry = await hass.helpers.entity_registry.async_get_registry()

    # Pre-create registry entries for sensors
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "my_random_entity_id",
        suggested_object_id="sensor.flipr_myfliprid_chlorine",
        disabled_by=None,
    )

    with patch(
        "flipr_api.FliprAPIRestClient.get_pool_measure_latest",
        return_value=MOCK_FLIPR_MEASURE,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.flipr_myfliprid_ph")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:pool"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "7.03"

    state = hass.states.get("sensor.flipr_myfliprid_water_temp")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is TEMP_CELSIUS
    assert state.state == "10.5"

    state = hass.states.get("sensor.flipr_myfliprid_last_measured")
    assert state
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2021-02-15T09:10:32+00:00"

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

"""Test the Flipr sensor."""

from datetime import datetime
from unittest.mock import patch

from flipr_api.exceptions import FliprError

from homeassistant.components.flipr.const import CONF_FLIPR_ID, DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_EMAIL,
    CONF_PASSWORD,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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
    "battery": 95.0,
}


async def test_sensors(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
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

    with patch(
        "flipr_api.FliprAPIRestClient.get_pool_measure_latest",
        return_value=MOCK_FLIPR_MEASURE,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Check entity unique_id value that is generated in FliprEntity base class.
    entity = entity_registry.async_get("sensor.flipr_myfliprid_red_ox")
    assert entity.unique_id == "myfliprid-red_ox"

    state = hass.states.get("sensor.flipr_myfliprid_ph")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "7.03"

    state = hass.states.get("sensor.flipr_myfliprid_water_temperature")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "10.5"

    state = hass.states.get("sensor.flipr_myfliprid_last_measured")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.state == "2021-02-15T09:10:32+00:00"

    state = hass.states.get("sensor.flipr_myfliprid_red_ox")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "mV"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "657.58"

    state = hass.states.get("sensor.flipr_myfliprid_chlorine")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "mV"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "0.23654886"

    state = hass.states.get("sensor.flipr_myfliprid_battery")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.state == "95.0"


async def test_error_flipr_api_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the Flipr sensors error."""
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

    with patch(
        "flipr_api.FliprAPIRestClient.get_pool_measure_latest",
        side_effect=FliprError("Error during flipr data retrieval..."),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Check entity is not generated because of the FliprError raised.
    entity = entity_registry.async_get("sensor.flipr_myfliprid_red_ox")
    assert entity is None

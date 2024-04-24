"""Test the Flipr binary sensor."""
from datetime import datetime
from unittest.mock import patch

from homeassistant.components.flipr.const import CONF_FLIPR_ID, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
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
}


async def test_sensors(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test the creation and values of the Flipr binary sensors."""
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
    entity = entity_registry.async_get("binary_sensor.flipr_myfliprid_ph_status")
    assert entity.unique_id == "myfliprid-ph_status"

    state = hass.states.get("binary_sensor.flipr_myfliprid_ph_status")
    assert state
    assert state.state == "on"  # Alert is on for binary sensor

    state = hass.states.get("binary_sensor.flipr_myfliprid_chlorine_status")
    assert state
    assert state.state == "off"

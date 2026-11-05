"""Define tests for SimpliSafe binary sensor entities."""

from copy import deepcopy

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonObjectType

ENTRY_SENSOR_SERIAL = "825"
DOOR_ENTITY_ID = "binary_sensor.fire_door_entry_door"
BATTERY_ENTITY_ID = "binary_sensor.fire_door_entry_battery"


@pytest.fixture(name="data_sensor")
def data_sensor_fixture(request: pytest.FixtureRequest) -> JsonObjectType:
    """Define sensor data with the entry sensor's offline flag set."""
    data = deepcopy(load_json_object_fixture("sensor_data.json", "simplisafe"))
    data[ENTRY_SENSOR_SERIAL]["flags"]["offline"] = request.param
    return data


@pytest.mark.parametrize(
    ("data_sensor", "expected_state"),
    [
        pytest.param(False, STATE_OFF, id="online"),
        pytest.param(True, STATE_UNAVAILABLE, id="offline"),
    ],
    indirect=["data_sensor"],
)
@pytest.mark.usefixtures("patch_simplisafe_api")
async def test_entry_sensor_offline(
    hass: HomeAssistant, config_entry: MockConfigEntry, expected_state: str
) -> None:
    """Test an entry sensor reported offline by SimpliSafe is unavailable."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    door_state = hass.states.get(DOOR_ENTITY_ID)
    assert door_state is not None
    assert door_state.state == expected_state

    battery_state = hass.states.get(BATTERY_ENTITY_ID)
    assert battery_state is not None
    assert battery_state.state == expected_state

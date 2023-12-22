"""The test for the Trafikverket train sensor platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytrafikverket.trafikverket_train import TrainStop

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


async def test_sensor_next(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_trains_next: list[TrainStop],
) -> None:
    """Test the Trafikverket Train sensor."""
    state1 = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time")
    state2 = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_state")
    state3 = hass.states.get("sensor.stockholm_c_to_uppsala_c_actual_time")
    state4 = hass.states.get("sensor.stockholm_c_to_uppsala_c_other_information")
    state5 = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_next")
    state6 = hass.states.get(
        "sensor.stockholm_c_to_uppsala_c_departure_time_next_after"
    )

    assert state1.state == "2023-05-01T12:00:00+00:00"
    assert state2.state == "on_time"
    assert state3.state == "2023-05-01T12:00:00+00:00"
    assert state4.state == "Some other info"
    assert state5.state == "2023-05-01T12:15:00+00:00"
    assert state6.state == "2023-05-01T12:30:00+00:00"

    assert state1.attributes["icon"] == "mdi:clock"
    assert state1.attributes["product_filter"] == "Regionaltåg"
    assert state2.attributes["icon"] == "mdi:clock"

    with patch(
        "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
        return_value=get_trains_next,
    ):
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state1 = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time")
    assert state1.state == "2023-05-01T17:00:00+00:00"
    state2 = hass.states.get("sensor.stockholm_c_to_uppsala_c_other_information")
    assert state2.state == STATE_UNKNOWN


async def test_sensor_single_stop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_trains_next: list[TrainStop],
) -> None:
    """Test the Trafikverket Train sensor."""
    state1 = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_2")

    assert state1.state == "2023-05-01T11:00:00+00:00"

    assert state1.attributes["icon"] == "mdi:clock"
    assert "product_filter" not in state1.attributes

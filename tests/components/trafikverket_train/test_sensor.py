"""The test for the Trafikverket train sensor platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytrafikverket.exceptions import InvalidAuthentication, NoTrainAnnouncementFound
from pytrafikverket.trafikverket_train import TrainStop
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


async def test_sensor_next(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_trains_next: list[TrainStop],
    get_train_stop: TrainStop,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Trafikverket Train sensor."""
    for entity in (
        "sensor.stockholm_c_to_uppsala_c_departure_time",
        "sensor.stockholm_c_to_uppsala_c_departure_state",
        "sensor.stockholm_c_to_uppsala_c_actual_time",
        "sensor.stockholm_c_to_uppsala_c_other_information",
        "sensor.stockholm_c_to_uppsala_c_departure_time_next",
        "sensor.stockholm_c_to_uppsala_c_departure_time_next_after",
    ):
        state = hass.states.get(entity)
        assert state == snapshot

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
            return_value=get_trains_next,
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_train_stop",
            return_value=get_train_stop,
        ),
    ):
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for entity in (
        "sensor.stockholm_c_to_uppsala_c_departure_time",
        "sensor.stockholm_c_to_uppsala_c_departure_state",
        "sensor.stockholm_c_to_uppsala_c_actual_time",
        "sensor.stockholm_c_to_uppsala_c_other_information",
        "sensor.stockholm_c_to_uppsala_c_departure_time_next",
        "sensor.stockholm_c_to_uppsala_c_departure_time_next_after",
    ):
        state = hass.states.get(entity)
        assert state == snapshot


async def test_sensor_single_stop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_trains_next: list[TrainStop],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Trafikverket Train sensor."""
    state = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_2")

    assert state.state == "2023-05-01T11:00:00+00:00"

    assert state == snapshot


async def test_sensor_update_auth_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_trains_next: list[TrainStop],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Trafikverket Train sensor with authentication update failure."""
    state = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_2")
    assert state.state == "2023-05-01T11:00:00+00:00"

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
            side_effect=InvalidAuthentication,
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_train_stop",
            side_effect=InvalidAuthentication,
        ),
    ):
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_2")
    assert state.state == STATE_UNAVAILABLE
    active_flows = load_int.async_get_active_flows(hass, (SOURCE_REAUTH))
    for flow in active_flows:
        assert flow == snapshot


async def test_sensor_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_trains_next: list[TrainStop],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Trafikverket Train sensor with update failure."""
    state = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_2")
    assert state.state == "2023-05-01T11:00:00+00:00"

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
            side_effect=NoTrainAnnouncementFound,
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_train_stop",
            side_effect=NoTrainAnnouncementFound,
        ),
    ):
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_2")
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_update_failure_no_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry_enabled_by_default: None,
    load_int: ConfigEntry,
    get_trains_next: list[TrainStop],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Trafikverket Train sensor with update failure from empty state."""
    state = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_2")
    assert state.state == "2023-05-01T11:00:00+00:00"

    with patch(
        "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_train_stop",
        return_value=None,
    ):
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.stockholm_c_to_uppsala_c_departure_time_2")
    assert state.state == STATE_UNAVAILABLE

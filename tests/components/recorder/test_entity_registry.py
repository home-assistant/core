"""The tests for sensor recorder platform."""
from collections.abc import Callable

import pytest
from sqlalchemy import select

from homeassistant.components import recorder
from homeassistant.components.recorder import history
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import setup_component
from homeassistant.util import dt as dt_util

from .common import (
    assert_dict_of_states_equal_without_context_and_last_changed,
    record_states,
    wait_recording_done,
)

from tests.common import mock_registry


def test_rename_entity(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
    """Test states meta is migrated when entity_id is changed."""
    hass = hass_recorder()
    setup_component(hass, "sensor", {})

    entity_reg = mock_registry(hass)

    @callback
    def add_entry():
        reg_entry = entity_reg.async_get_or_create(
            "sensor",
            "test",
            "unique_0000",
            suggested_object_id="test1",
        )
        assert reg_entry.entity_id == "sensor.test1"

    hass.add_job(add_entry)
    hass.block_till_done()

    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)

    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    @callback
    def rename_entry():
        entity_reg.async_update_entity("sensor.test1", new_entity_id="sensor.test99")

    hass.add_job(rename_entry)
    wait_recording_done(hass)

    hist = history.get_significant_states(hass, zero, four)
    states["sensor.test99"] = states.pop("sensor.test1")
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    hass.states.set("sensor.test99", "post_migrate")
    wait_recording_done(hass)
    new_hist = history.get_significant_states(hass, zero, dt_util.utcnow())
    assert new_hist["sensor.test99"][-1].state == "post_migrate"

    with session_scope(hass=hass) as session:
        assert (
            len(
                list(
                    session.execute(
                        select(recorder.db_schema.StatesMeta).filter(
                            recorder.db_schema.StatesMeta.entity_id == "sensor.test99"
                        )
                    )
                )
            )
            == 1
        )
    assert "the new entity_id is already in use" not in caplog.text


def test_rename_entity_collision(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
    """Test states meta is not migrated when there is a collision."""
    hass = hass_recorder()
    setup_component(hass, "sensor", {})

    entity_reg = mock_registry(hass)

    @callback
    def add_entry():
        reg_entry = entity_reg.async_get_or_create(
            "sensor",
            "test",
            "unique_0000",
            suggested_object_id="test1",
        )
        assert reg_entry.entity_id == "sensor.test1"

    hass.add_job(add_entry)
    hass.block_till_done()

    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    hass.states.set("sensor.test99", "collision")
    hass.states.remove("sensor.test99")

    hass.block_till_done()

    # Rename entity sensor.test1 to sensor.test99
    @callback
    def rename_entry():
        entity_reg.async_update_entity("sensor.test1", new_entity_id="sensor.test99")

    hass.add_job(rename_entry)
    wait_recording_done(hass)

    # History is not migrated on collision
    hist = history.get_significant_states(hass, zero, four)
    states["sensor.test99"] = states.pop("sensor.test1")

    assert len(hist["sensor.test99"]) == 2

    hass.states.set("sensor.test99", "post_migrate")
    wait_recording_done(hass)
    new_hist = history.get_significant_states(hass, zero, dt_util.utcnow())
    assert new_hist["sensor.test99"][-1].state == "post_migrate"

    with session_scope(hass=hass) as session:
        assert (
            len(
                list(
                    session.execute(
                        select(recorder.db_schema.StatesMeta).filter(
                            recorder.db_schema.StatesMeta.entity_id == "sensor.test99"
                        )
                    )
                )
            )
            == 1
        )

    assert "the new entity_id is already in use" in caplog.text

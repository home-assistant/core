"""The tests for sensor recorder platform."""

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder, history
from homeassistant.components.recorder.db_schema import StatesMeta
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import (
    ForceReturnConnectionToPool,
    assert_dict_of_states_equal_without_context_and_last_changed,
    async_record_states,
    async_wait_recording_done,
)

from tests.common import MockEntity, MockEntityPlatform
from tests.typing import RecorderInstanceGenerator


def _count_entity_id_in_states_meta(
    hass: HomeAssistant, session: Session, entity_id: str
) -> int:
    return len(
        list(
            session.execute(
                select(StatesMeta).filter(StatesMeta.entity_id == "sensor.test99")
            )
        )
    )


@pytest.fixture
async def mock_recorder_before_hass(
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Set up recorder."""


@pytest.fixture(autouse=True)
def setup_recorder(recorder_mock: Recorder) -> recorder.Recorder:
    """Set up recorder."""


async def test_rename_entity_without_collision(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test states meta is migrated when entity_id is changed."""
    await async_setup_component(hass, "sensor", {})

    reg_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_0000",
        suggested_object_id="test1",
    )
    assert reg_entry.entity_id == "sensor.test1"
    await hass.async_block_till_done()

    zero, four, states = await async_record_states(hass)
    hist = history.get_significant_states(
        hass, zero, four, list(set(states) | {"sensor.test99", "sensor.test1"})
    )

    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    entity_registry.async_update_entity("sensor.test1", new_entity_id="sensor.test99")
    await async_wait_recording_done(hass)

    hist = history.get_significant_states(
        hass, zero, four, list(set(states) | {"sensor.test99", "sensor.test1"})
    )
    states["sensor.test99"] = states.pop("sensor.test1")
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    hass.states.async_set("sensor.test99", "post_migrate")
    await async_wait_recording_done(hass)
    new_hist = history.get_significant_states(
        hass,
        zero,
        dt_util.utcnow(),
        list(set(states) | {"sensor.test99", "sensor.test1"}),
    )
    assert not new_hist.get("sensor.test1")
    assert new_hist["sensor.test99"][-1].state == "post_migrate"

    with session_scope(hass=hass) as session:
        assert _count_entity_id_in_states_meta(hass, session, "sensor.test99") == 1
        assert _count_entity_id_in_states_meta(hass, session, "sensor.test1") == 1

    assert "the new entity_id is already in use" not in caplog.text


async def test_rename_entity_on_mocked_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test states meta is migrated when entity_id is changed when using a mocked platform.

    This test will call async_remove on the entity so we can make
    sure that we do not record the entity as removed in the database
    when we rename it.
    """
    instance = recorder.get_instance(hass)
    start = dt_util.utcnow()

    reg_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_0000",
        suggested_object_id="test1",
    )
    assert reg_entry.entity_id == "sensor.test1"

    entity_platform1 = MockEntityPlatform(
        hass, domain="mock_integration", platform_name="mock_platform", platform=None
    )
    entity1 = MockEntity(entity_id=reg_entry.entity_id)
    await entity_platform1.async_add_entities([entity1])

    await hass.async_block_till_done()

    hass.states.async_set("sensor.test1", "pre_migrate")
    await async_wait_recording_done(hass)

    hist = await instance.async_add_executor_job(
        history.get_significant_states,
        hass,
        start,
        None,
        ["sensor.test1", "sensor.test99"],
    )

    entity_registry.async_update_entity("sensor.test1", new_entity_id="sensor.test99")
    await hass.async_block_till_done()
    # We have to call the remove method ourselves since we are mocking the platform
    hass.states.async_remove("sensor.test1")

    # The remove will trigger a lookup of the non-existing entity_id in the database
    # so we need to force the recorder to return the connection to the pool
    # since our test setup only allows one connection at a time.
    instance.queue_task(ForceReturnConnectionToPool())

    await async_wait_recording_done(hass)

    hist = await instance.async_add_executor_job(
        history.get_significant_states,
        hass,
        start,
        None,
        ["sensor.test1", "sensor.test99"],
    )

    assert "sensor.test1" not in hist
    # Make sure the states manager has not leaked the old entity_id
    assert instance.states_manager.pop_committed("sensor.test1") is None
    assert instance.states_manager.pop_pending("sensor.test1") is None

    hass.states.async_set("sensor.test99", "post_migrate")
    await async_wait_recording_done(hass)

    new_hist = await instance.async_add_executor_job(
        history.get_significant_states,
        hass,
        start,
        None,
        ["sensor.test1", "sensor.test99"],
    )

    assert "sensor.test1" not in new_hist
    assert new_hist["sensor.test99"][-1].state == "post_migrate"

    def _get_states_meta_counts():
        with session_scope(hass=hass) as session:
            return _count_entity_id_in_states_meta(
                hass, session, "sensor.test99"
            ), _count_entity_id_in_states_meta(hass, session, "sensor.test1")

    test99_count, test1_count = await instance.async_add_executor_job(
        _get_states_meta_counts
    )
    assert test99_count == 1
    assert test1_count == 1

    assert "the new entity_id is already in use" not in caplog.text


async def test_rename_entity_collision(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test states meta is not migrated when there is a collision."""
    await async_setup_component(hass, "sensor", {})

    reg_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_0000",
        suggested_object_id="test1",
    )
    assert reg_entry.entity_id == "sensor.test1"
    await hass.async_block_till_done()

    zero, four, states = await async_record_states(hass)
    hist = history.get_significant_states(
        hass, zero, four, list(set(states) | {"sensor.test99", "sensor.test1"})
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)
    assert len(hist["sensor.test1"]) == 3

    hass.states.async_set("sensor.test99", "collision")
    hass.states.async_remove("sensor.test99")

    await hass.async_block_till_done()

    # Rename entity sensor.test1 to sensor.test99
    entity_registry.async_update_entity("sensor.test1", new_entity_id="sensor.test99")
    await async_wait_recording_done(hass)

    # History is not migrated on collision
    hist = history.get_significant_states(
        hass, zero, four, list(set(states) | {"sensor.test99", "sensor.test1"})
    )
    assert len(hist["sensor.test1"]) == 3
    assert len(hist["sensor.test99"]) == 2

    with session_scope(hass=hass) as session:
        assert _count_entity_id_in_states_meta(hass, session, "sensor.test99") == 1

    hass.states.async_set("sensor.test99", "post_migrate")
    await async_wait_recording_done(hass)
    new_hist = history.get_significant_states(
        hass,
        zero,
        dt_util.utcnow(),
        list(set(states) | {"sensor.test99", "sensor.test1"}),
    )
    assert new_hist["sensor.test99"][-1].state == "post_migrate"
    assert len(hist["sensor.test99"]) == 2

    with session_scope(hass=hass) as session:
        assert _count_entity_id_in_states_meta(hass, session, "sensor.test99") == 1
        assert _count_entity_id_in_states_meta(hass, session, "sensor.test1") == 1

    # We should hit the safeguard in the states_meta_manager
    assert "the new entity_id is already in use" in caplog.text

    # We should not hit the safeguard in the entity_registry
    assert "Blocked attempt to insert duplicated state rows" not in caplog.text


async def test_rename_entity_collision_without_states_meta_safeguard(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test states meta is not migrated when there is a collision.

    This test disables the safeguard in the states_meta_manager
    and relies on the filter_unique_constraint_integrity_error safeguard.
    """
    await async_setup_component(hass, "sensor", {})

    reg_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_0000",
        suggested_object_id="test1",
    )
    assert reg_entry.entity_id == "sensor.test1"
    await hass.async_block_till_done()

    zero, four, states = await async_record_states(hass)
    hist = history.get_significant_states(
        hass, zero, four, list(set(states) | {"sensor.test99", "sensor.test1"})
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)
    assert len(hist["sensor.test1"]) == 3

    hass.states.async_set("sensor.test99", "collision")
    hass.states.async_remove("sensor.test99")

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # Verify history before collision
    hist = history.get_significant_states(
        hass, zero, four, list(set(states) | {"sensor.test99", "sensor.test1"})
    )
    assert len(hist["sensor.test1"]) == 3
    assert len(hist["sensor.test99"]) == 2

    instance = recorder.get_instance(hass)
    # Patch out the safeguard in the states meta manager
    # so that we hit the filter_unique_constraint_integrity_error safeguard in the entity_registry
    with patch.object(instance.states_meta_manager, "get", return_value=None):
        # Rename entity sensor.test1 to sensor.test99
        entity_registry.async_update_entity(
            "sensor.test1", new_entity_id="sensor.test99"
        )
        await async_wait_recording_done(hass)

    # History is not migrated on collision
    hist = history.get_significant_states(
        hass, zero, four, list(set(states) | {"sensor.test99", "sensor.test1"})
    )
    assert len(hist["sensor.test1"]) == 3
    assert len(hist["sensor.test99"]) == 2

    with session_scope(hass=hass) as session:
        assert _count_entity_id_in_states_meta(hass, session, "sensor.test99") == 1

    hass.states.async_set("sensor.test99", "post_migrate")
    await async_wait_recording_done(hass)

    new_hist = history.get_significant_states(
        hass,
        zero,
        dt_util.utcnow(),
        list(set(states) | {"sensor.test99", "sensor.test1"}),
    )
    assert new_hist["sensor.test99"][-1].state == "post_migrate"
    assert len(hist["sensor.test99"]) == 2

    with session_scope(hass=hass) as session:
        assert _count_entity_id_in_states_meta(hass, session, "sensor.test99") == 1
        assert _count_entity_id_in_states_meta(hass, session, "sensor.test1") == 1

    # We should not hit the safeguard in the states_meta_manager
    assert "the new entity_id is already in use" not in caplog.text

    # We should hit the safeguard in the entity_registry
    assert "Blocked attempt to insert duplicated state rows" in caplog.text

"""The tests for the recorder event types manager."""

from unittest.mock import patch

import pytest

from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant

from tests.typing import RecorderInstanceGenerator


@pytest.mark.parametrize(
    ("from_recorder", "expected_task_queued"),
    [
        pytest.param(True, False, id="from_recorder"),
        pytest.param(False, True, id="not_from_recorder"),
    ],
)
async def test_get_non_existent_event_type(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    from_recorder: bool,
    expected_task_queued: bool,
) -> None:
    """Test getting a non-existent event type only queues a refresh when needed."""
    instance = await async_setup_recorder_instance(hass)
    manager = instance.event_type_manager

    with (
        session_scope(session=instance.get_session()) as session,
        patch.object(instance, "queue_task") as mock_queue_task,
    ):
        assert manager.get("unknown_event_type", session, from_recorder) is None

    assert mock_queue_task.called == expected_task_queued
    assert ("unknown_event_type" in manager._non_existent_event_types) is (
        not expected_task_queued
    )

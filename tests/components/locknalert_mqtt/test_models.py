"""Tests for locknalert_mqtt models module."""

import logging
from unittest.mock import MagicMock

import pytest

from homeassistant.components.locknalert_mqtt.models import EntityTopicState


def _make_msg(topic: str = "test/topic", payload: bytes = b"data") -> MagicMock:
    """Return a minimal paho MQTTMessage stand-in."""
    msg = MagicMock()
    msg.topic = topic
    msg.payload = payload
    return msg


# ---------------------------------------------------------------------------
# EntityTopicState.write_state_request
# ---------------------------------------------------------------------------


def test_write_state_request_stores_entity() -> None:
    """write_state_request registers the entity by entity_id."""
    state = EntityTopicState()
    entity = MagicMock()
    entity.entity_id = "alarm_control_panel.test"
    state.write_state_request(entity)
    assert state.subscribe_calls["alarm_control_panel.test"] is entity


def test_write_state_request_is_idempotent() -> None:
    """Registering the same entity twice keeps only the last reference."""
    state = EntityTopicState()
    entity1 = MagicMock()
    entity2 = MagicMock()
    entity1.entity_id = "alarm_control_panel.test"
    entity2.entity_id = "alarm_control_panel.test"
    state.write_state_request(entity1)
    state.write_state_request(entity2)
    assert len(state.subscribe_calls) == 1
    assert state.subscribe_calls["alarm_control_panel.test"] is entity2


# ---------------------------------------------------------------------------
# EntityTopicState.process_write_state_requests — happy path
# ---------------------------------------------------------------------------


def test_process_write_state_requests_calls_write_ha_state() -> None:
    """process_write_state_requests calls async_write_ha_state on each entity."""
    state = EntityTopicState()
    entity = MagicMock()
    entity.entity_id = "alarm_control_panel.test"
    state.write_state_request(entity)
    state.process_write_state_requests(_make_msg())
    entity.async_write_ha_state.assert_called_once()
    assert not state.subscribe_calls


def test_process_write_state_requests_noop_when_empty() -> None:
    """process_write_state_requests does nothing when no entities are pending."""
    state = EntityTopicState()
    state.process_write_state_requests(_make_msg())


# ---------------------------------------------------------------------------
# EntityTopicState.process_write_state_requests — exception paths
# ---------------------------------------------------------------------------


def test_process_write_state_requests_logs_value_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """process_write_state_requests logs a ValueError raised by async_write_ha_state."""
    state = EntityTopicState()
    entity = MagicMock()
    entity.entity_id = "alarm_control_panel.bad"
    entity.async_write_ha_state.side_effect = ValueError("bad state value")

    with caplog.at_level(
        logging.ERROR, logger="homeassistant.components.locknalert_mqtt"
    ):
        state.write_state_request(entity)
        state.process_write_state_requests(_make_msg())

    assert "Value error while updating state of" in caplog.text
    assert "alarm_control_panel.bad" in caplog.text


def test_process_write_state_requests_logs_unexpected_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """process_write_state_requests logs any other exception raised by async_write_ha_state."""
    state = EntityTopicState()
    entity = MagicMock()
    entity.entity_id = "alarm_control_panel.crash"
    entity.async_write_ha_state.side_effect = RuntimeError("internal crash")

    with caplog.at_level(
        logging.ERROR, logger="homeassistant.components.locknalert_mqtt"
    ):
        state.write_state_request(entity)
        state.process_write_state_requests(_make_msg())

    assert "Exception raised while updating state of" in caplog.text
    assert "alarm_control_panel.crash" in caplog.text


def test_process_write_state_requests_continues_after_error() -> None:
    """process_write_state_requests processes all entities even when one raises."""
    state = EntityTopicState()
    entity_bad = MagicMock()
    entity_bad.entity_id = "alarm_control_panel.bad"
    entity_bad.async_write_ha_state.side_effect = ValueError("bad")
    entity_good = MagicMock()
    entity_good.entity_id = "alarm_control_panel.good"

    state.write_state_request(entity_bad)
    state.write_state_request(entity_good)
    state.process_write_state_requests(_make_msg())

    entity_good.async_write_ha_state.assert_called_once()

"""The tests for the logbook component models."""

from unittest.mock import Mock

from homeassistant.components.logbook.models import EventAsRow, LazyEventPartialState


def test_lazy_event_partial_state_context() -> None:
    """Test we can extract context from a lazy event partial state."""
    state = LazyEventPartialState(
        EventAsRow(
            row_id=1,
            event_type="event_type",
            event_data={},
            time_fired_ts=1,
            context_id_bin=b"1234123412341234",
            context_user_id_bin=b"1234123412341234",
            context_parent_id_bin=b"4444444444444444",
            state="state",
            entity_id="entity_id",
            icon="icon",
            context_only=False,
            data={},
            context=Mock(),
        ),
        {},
    )
    assert state.context_id == "1H68SK8C9J6CT32CHK6GRK4CSM"
    assert state.context_user_id == "31323334313233343132333431323334"
    assert state.context_parent_id == "1M6GT38D1M6GT38D1M6GT38D1M"
    assert state.event_type == "event_type"
    assert state.entity_id == "entity_id"
    assert state.state == "state"

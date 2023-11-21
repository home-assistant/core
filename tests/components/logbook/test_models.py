"""The tests for the logbook component models."""
from unittest.mock import Mock

from homeassistant.components.logbook.models import LazyEventPartialState


def test_lazy_event_partial_state_context():
    """Test we can extract context from a lazy event partial state."""
    state = LazyEventPartialState(
        Mock(
            context_id_bin=b"1234123412341234",
            context_user_id_bin=b"1234123412341234",
            context_parent_id_bin=b"4444444444444444",
            event_data={},
        ),
        {},
    )
    assert state.context_id == "1H68SK8C9J6CT32CHK6GRK4CSM"
    assert state.context_user_id == "31323334313233343132333431323334"
    assert state.context_parent_id == "1M6GT38D1M6GT38D1M6GT38D1M"

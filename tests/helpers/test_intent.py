"""Tests for the intent helpers."""
from homeassistant.core import State
from homeassistant.helpers import intent


def test_async_match_state():
    """Test async_match_state helper."""
    state1 = State('light.kitchen', 'on')
    state2 = State('switch.kitchen', 'on')

    state = intent.async_match_state(None, 'kitch', [state1, state2])
    assert state is state1

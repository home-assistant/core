"""Tests for the init."""
from homeassistant.const import (
    EVENT_CALL_SERVICE, ATTR_SERVICE_DATA, ATTR_ENTITY_ID)
from homeassistant.components.suggestions import _generate_suggestion
from homeassistant.util import dt as dt_util

from tests.common_recorder import MockEvent

NIGHT = dt_util.now().replace(hour=2)
MORNING = dt_util.now().replace(hour=8)
AFTERNOON = dt_util.now().replace(hour=14)
EVENING = dt_util.now().replace(hour=20)
EMPTY = {
    'morning': [],
    'afternoon': [],
    'evening': [],
    'night': [],
}


def _mock_service(entity_id, time_fired, context_id=None):
    """Create a mock service event."""
    return MockEvent(
        event_type=EVENT_CALL_SERVICE,
        event_data={
            ATTR_SERVICE_DATA: {
                ATTR_ENTITY_ID: entity_id
            }
        },
        time_fired=time_fired,
        context_id=context_id
    )


def test_suggestions_call_service(hass, mock_recorder_results):
    """Test call service entities being translated."""
    mock_recorder_results.extend([
        _mock_service('light.night', NIGHT),
        _mock_service('light.morning', MORNING),
        _mock_service('light.afternoon', AFTERNOON),
        _mock_service('light.evening', EVENING),
    ])
    suggestions = _generate_suggestion(hass)
    assert suggestions['night'] == ['light.night']
    assert suggestions['morning'] == ['light.morning']
    assert suggestions['afternoon'] == ['light.afternoon']
    assert suggestions['evening'] == ['light.evening']


def test_ignoring_subsequent_context_id(hass, mock_recorder_results):
    """Test we ignore service calls as result of scene or script."""
    context_id = 'morning-script-context'
    mock_recorder_results.extend([
        _mock_service('script.morning', MORNING, context_id=context_id),
        _mock_service('light.kitchen', MORNING, context_id=context_id),
        _mock_service('cover.kitchen', MORNING, context_id=context_id),
    ])
    suggestions = _generate_suggestion(hass)
    assert suggestions['morning'] == ['script.morning']


def test_popular_first(hass, mock_recorder_results):
    """Test call service entities being translated."""
    mock_recorder_results.extend([
        _mock_service('cover.kitchen', MORNING),
        _mock_service('light.kitchen', MORNING),
        _mock_service('light.kitchen', MORNING),
    ])
    suggestions = _generate_suggestion(hass)
    assert suggestions['morning'] == ['light.kitchen', 'cover.kitchen']


def test_bad_services(hass, mock_recorder_results):
    """Test service with bad data."""
    mock_recorder_results.append(
        MockEvent(
            event_type=EVENT_CALL_SERVICE,
            event_data_raw='invalid json',
        )
    )
    # Should not raise
    assert _generate_suggestion(hass) == EMPTY

    mock_recorder_results.clear()
    mock_recorder_results.append(
        MockEvent(
            event_type=EVENT_CALL_SERVICE,
            event_data={},
        )
    )
    # Should not raise
    assert _generate_suggestion(hass) == EMPTY

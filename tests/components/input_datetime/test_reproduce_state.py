"""Test reproduce state for Input datetime."""

import pytest

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Input datetime states."""
    hass.states.async_set(
        "input_datetime.entity_datetime",
        "2010-10-10 01:20:00",
        {"has_date": True, "has_time": True},
    )
    hass.states.async_set(
        "input_datetime.entity_time", "01:20:00", {"has_date": False, "has_time": True}
    )
    hass.states.async_set(
        "input_datetime.entity_date",
        "2010-10-10",
        {"has_date": True, "has_time": False},
    )
    hass.states.async_set(
        "input_datetime.invalid_data",
        "unavailable",
        {"has_date": False, "has_time": False},
    )

    datetime_calls = async_mock_service(hass, "input_datetime", "set_datetime")

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("input_datetime.entity_datetime", "2010-10-10 01:20:00"),
            State("input_datetime.entity_time", "01:20:00"),
            State("input_datetime.entity_date", "2010-10-10"),
        ],
    )

    assert len(datetime_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(
        hass,
        [
            State("input_datetime.entity_datetime", "not_supported"),
            State("input_datetime.entity_datetime", "not-valid-date"),
            State("input_datetime.entity_datetime", "not:valid:time"),
            State("input_datetime.entity_datetime", "1234-56-78 90:12:34"),
        ],
    )

    assert "not_supported" in caplog.text
    assert "not-valid-date" in caplog.text
    assert "not:valid:time" in caplog.text
    assert "1234-56-78 90:12:34" in caplog.text
    assert len(datetime_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("input_datetime.entity_datetime", "2011-10-10 02:20:00"),
            State("input_datetime.entity_time", "02:20:00"),
            State("input_datetime.entity_date", "2011-10-10"),
            # Should not raise
            State("input_datetime.non_existing", "2010-10-10 01:20:00"),
            State("input_datetime.invalid_data", "2010-10-10 01:20:00"),
        ],
    )

    valid_calls = [
        {
            "entity_id": "input_datetime.entity_datetime",
            "datetime": "2011-10-10 02:20:00",
        },
        {"entity_id": "input_datetime.entity_time", "time": "02:20:00"},
        {"entity_id": "input_datetime.entity_date", "date": "2011-10-10"},
    ]
    assert len(datetime_calls) == 3
    for call in datetime_calls:
        assert call.domain == "input_datetime"
        assert call.data in valid_calls
        valid_calls.remove(call.data)

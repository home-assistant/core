"""Test reproduce state for Cover."""

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Cover states."""
    hass.states.async_set(
        "cover.entity_close",
        CoverState.CLOSED,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN,
        },
    )
    hass.states.async_set(
        "cover.closed_only_supports_close_open",
        CoverState.CLOSED,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN,
        },
    )
    hass.states.async_set(
        "cover.closed_only_supports_tilt_close_open",
        CoverState.CLOSED,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT,
        },
    )
    hass.states.async_set(
        "cover.entity_close_attr",
        CoverState.CLOSED,
        {
            ATTR_CURRENT_POSITION: 0,
            ATTR_CURRENT_TILT_POSITION: 0,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN,
        },
    )
    hass.states.async_set(
        "cover.entity_close_tilt",
        CoverState.CLOSED,
        {
            ATTR_CURRENT_TILT_POSITION: 50,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        },
    )
    hass.states.async_set(
        "cover.entity_open",
        CoverState.OPEN,
        {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN},
    )
    hass.states.async_set(
        "cover.entity_slightly_open",
        CoverState.OPEN,
        {
            ATTR_CURRENT_POSITION: 50,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN,
        },
    )
    hass.states.async_set(
        "cover.entity_open_attr",
        CoverState.OPEN,
        {
            ATTR_CURRENT_POSITION: 100,
            ATTR_CURRENT_TILT_POSITION: 0,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN,
        },
    )
    hass.states.async_set(
        "cover.entity_open_tilt",
        CoverState.OPEN,
        {
            ATTR_CURRENT_POSITION: 50,
            ATTR_CURRENT_TILT_POSITION: 50,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN,
        },
    )
    hass.states.async_set(
        "cover.entity_entirely_open",
        CoverState.OPEN,
        {
            ATTR_CURRENT_POSITION: 100,
            ATTR_CURRENT_TILT_POSITION: 100,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN,
        },
    )
    hass.states.async_set(
        "cover.tilt_only_open",
        CoverState.OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT,
        },
    )
    hass.states.async_set(
        "cover.tilt_only_closed",
        CoverState.CLOSED,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT,
        },
    )
    hass.states.async_set(
        "cover.tilt_only_tilt_position_100",
        CoverState.OPEN,
        {
            ATTR_CURRENT_TILT_POSITION: 100,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        },
    )
    hass.states.async_set(
        "cover.tilt_only_tilt_position_0",
        CoverState.CLOSED,
        {
            ATTR_CURRENT_TILT_POSITION: 0,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
        },
    )
    close_calls = async_mock_service(hass, "cover", SERVICE_CLOSE_COVER)
    open_calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER)
    close_tilt_calls = async_mock_service(hass, "cover", SERVICE_CLOSE_COVER_TILT)
    open_tilt_calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER_TILT)
    position_calls = async_mock_service(hass, "cover", SERVICE_SET_COVER_POSITION)
    position_tilt_calls = async_mock_service(
        hass, "cover", SERVICE_SET_COVER_TILT_POSITION
    )

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("cover.entity_close", CoverState.CLOSED),
            State("cover.closed_only_supports_close_open", CoverState.CLOSED),
            State("cover.closed_only_supports_tilt_close_open", CoverState.CLOSED),
            State(
                "cover.entity_close_attr",
                CoverState.CLOSED,
                {ATTR_CURRENT_POSITION: 0, ATTR_CURRENT_TILT_POSITION: 0},
            ),
            State(
                "cover.entity_close_tilt",
                CoverState.CLOSED,
                {ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State("cover.entity_open", CoverState.OPEN),
            State(
                "cover.entity_slightly_open",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 50},
            ),
            State(
                "cover.entity_open_attr",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 100, ATTR_CURRENT_TILT_POSITION: 0},
            ),
            State(
                "cover.entity_open_tilt",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 50, ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State(
                "cover.entity_entirely_open",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 100, ATTR_CURRENT_TILT_POSITION: 100},
            ),
            State(
                "cover.tilt_only_open",
                CoverState.OPEN,
                {},
            ),
            State(
                "cover.tilt_only_tilt_position_100",
                CoverState.OPEN,
                {ATTR_CURRENT_TILT_POSITION: 100},
            ),
            State(
                "cover.tilt_only_closed",
                CoverState.CLOSED,
                {},
            ),
            State(
                "cover.tilt_only_tilt_position_0",
                CoverState.CLOSED,
                {ATTR_CURRENT_TILT_POSITION: 0},
            ),
        ],
    )

    assert len(close_calls) == 0
    assert len(open_calls) == 0
    assert len(close_tilt_calls) == 0
    assert len(open_tilt_calls) == 0
    assert len(position_calls) == 0
    assert len(position_tilt_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State("cover.entity_close", "not_supported")])

    assert "not_supported" in caplog.text
    assert len(close_calls) == 0
    assert len(open_calls) == 0
    assert len(close_tilt_calls) == 0
    assert len(open_tilt_calls) == 0
    assert len(position_calls) == 0
    assert len(position_tilt_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("cover.entity_close", CoverState.OPEN),
            State(
                "cover.closed_only_supports_close_open",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 100},
            ),
            State("cover.closed_only_supports_tilt_close_open", CoverState.OPEN),
            State(
                "cover.entity_close_attr",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 50, ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State(
                "cover.entity_close_tilt",
                CoverState.CLOSED,
                {ATTR_CURRENT_TILT_POSITION: 100},
            ),
            State("cover.entity_open", CoverState.CLOSED),
            State("cover.entity_slightly_open", CoverState.OPEN, {}),
            State("cover.entity_open_attr", CoverState.CLOSED, {}),
            State(
                "cover.entity_open_tilt",
                CoverState.OPEN,
                {ATTR_CURRENT_TILT_POSITION: 0},
            ),
            State(
                "cover.entity_entirely_open",
                CoverState.CLOSED,
                {ATTR_CURRENT_POSITION: 0, ATTR_CURRENT_TILT_POSITION: 0},
            ),
            # Should not raise
            State("cover.non_existing", "on"),
            State(
                "cover.tilt_only_open",
                CoverState.CLOSED,
                {},
            ),
            State(
                "cover.tilt_only_tilt_position_100",
                CoverState.CLOSED,
                {ATTR_CURRENT_TILT_POSITION: 0},
            ),
            State(
                "cover.tilt_only_closed",
                CoverState.OPEN,
                {},
            ),
            State(
                "cover.tilt_only_tilt_position_0",
                CoverState.OPEN,
                {ATTR_CURRENT_TILT_POSITION: 100},
            ),
        ],
    )

    valid_close_calls = [
        {"entity_id": "cover.entity_open"},
        {"entity_id": "cover.entity_open_attr"},
        {"entity_id": "cover.entity_entirely_open"},
    ]
    assert len(close_calls) == len(valid_close_calls)
    for call in close_calls:
        assert call.domain == "cover"
        assert call.data in valid_close_calls
        valid_close_calls.remove(call.data)

    valid_open_calls = [
        {"entity_id": "cover.entity_close"},
        {"entity_id": "cover.entity_slightly_open"},
        {"entity_id": "cover.entity_open_tilt"},
        {"entity_id": "cover.closed_only_supports_close_open"},
    ]
    assert len(open_calls) == len(valid_open_calls)
    for call in open_calls:
        assert call.domain == "cover"
        assert call.data in valid_open_calls
        valid_open_calls.remove(call.data)

    valid_close_tilt_calls = [
        {"entity_id": "cover.entity_open_tilt"},
        {"entity_id": "cover.entity_entirely_open"},
        {"entity_id": "cover.tilt_only_open"},
        {"entity_id": "cover.entity_open_attr"},
        {"entity_id": "cover.tilt_only_tilt_position_100"},
    ]
    assert len(close_tilt_calls) == len(valid_close_tilt_calls)
    for call in close_tilt_calls:
        assert call.domain == "cover"
        assert call.data in valid_close_tilt_calls
        valid_close_tilt_calls.remove(call.data)

    valid_open_tilt_calls = [
        {"entity_id": "cover.entity_close_tilt"},
        {"entity_id": "cover.tilt_only_closed"},
        {"entity_id": "cover.tilt_only_tilt_position_0"},
        {"entity_id": "cover.closed_only_supports_tilt_close_open"},
    ]
    assert len(open_tilt_calls) == len(valid_open_tilt_calls)
    for call in open_tilt_calls:
        assert call.domain == "cover"
        assert call.data in valid_open_tilt_calls
        valid_open_tilt_calls.remove(call.data)

    assert len(position_calls) == 1
    assert position_calls[0].domain == "cover"
    assert position_calls[0].data == {
        "entity_id": "cover.entity_close_attr",
        ATTR_POSITION: 50,
    }

    assert len(position_tilt_calls) == 1
    assert position_tilt_calls[0].domain == "cover"
    assert position_tilt_calls[0].data == {
        "entity_id": "cover.entity_close_attr",
        ATTR_TILT_POSITION: 50,
    }

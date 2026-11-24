"""Test reproduce state for Cover."""

from typing import Any

import pytest
from pytest_homeassistant.common import async_mock_service

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    CoverEntityCapabilityAttribute,
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
        "cover.open_only_supports_close_open",
        CoverState.OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN,
        },
    )
    hass.states.async_set(
        "cover.open_missing_all_features",
        CoverState.OPEN,
    )
    hass.states.async_set(
        "cover.closed_missing_all_features_has_position",
        CoverState.CLOSED,
        {
            ATTR_CURRENT_POSITION: 0,
        },
    )
    hass.states.async_set(
        "cover.open_missing_all_features_has_tilt_position",
        CoverState.OPEN,
        {
            ATTR_CURRENT_TILT_POSITION: 50,
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
        "cover.open_only_supports_tilt_close_open",
        CoverState.OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.OPEN_TILT,
        },
    )
    hass.states.async_set(
        "cover.closed_only_supports_position",
        CoverState.CLOSED,
        {
            ATTR_CURRENT_POSITION: 0,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        },
    )
    hass.states.async_set(
        "cover.open_only_supports_position",
        CoverState.OPEN,
        {ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION},
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
        "cover.closed_supports_all_features",
        CoverState.CLOSED,
        {
            ATTR_CURRENT_POSITION: 0,
            ATTR_CURRENT_TILT_POSITION: 0,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
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
    hass.states.async_set(
        "cover.tilt_open_only_supports_tilt_position",
        CoverState.OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_TILT_POSITION,
        },
    )
    hass.states.async_set(
        "cover.tilt_partial_open_only_supports_tilt_position",
        CoverState.OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_TILT_POSITION,
            ATTR_CURRENT_TILT_POSITION: 50,
        },
    )
    hass.states.async_set(
        "cover.tilt_closed_only_supports_tilt_position",
        CoverState.CLOSED,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_TILT_POSITION,
        },
    )
    close_calls = async_mock_service(hass, DOMAIN, SERVICE_CLOSE_COVER)
    open_calls = async_mock_service(hass, DOMAIN, SERVICE_OPEN_COVER)
    close_tilt_calls = async_mock_service(hass, DOMAIN, SERVICE_CLOSE_COVER_TILT)
    open_tilt_calls = async_mock_service(hass, DOMAIN, SERVICE_OPEN_COVER_TILT)
    position_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_COVER_POSITION)
    position_tilt_calls = async_mock_service(
        hass, DOMAIN, SERVICE_SET_COVER_TILT_POSITION
    )

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State(
                "cover.closed_supports_all_features",
                CoverState.CLOSED,
                {
                    ATTR_CURRENT_POSITION: 0,
                    ATTR_CURRENT_TILT_POSITION: 0,
                },
            ),
            State("cover.entity_close", CoverState.CLOSED),
            State("cover.closed_only_supports_close_open", CoverState.CLOSED),
            State("cover.closed_only_supports_tilt_close_open", CoverState.CLOSED),
            State("cover.open_only_supports_close_open", CoverState.OPEN),
            State("cover.open_only_supports_tilt_close_open", CoverState.OPEN),
            State("cover.open_missing_all_features", CoverState.OPEN),
            State(
                "cover.closed_missing_all_features_has_position",
                CoverState.CLOSED,
                {
                    ATTR_CURRENT_POSITION: 0,
                },
            ),
            State(
                "cover.open_missing_all_features_has_tilt_position",
                CoverState.OPEN,
                {
                    ATTR_CURRENT_TILT_POSITION: 50,
                },
            ),
            State(
                "cover.closed_only_supports_position",
                CoverState.CLOSED,
                {ATTR_CURRENT_POSITION: 0},
            ),
            State("cover.open_only_supports_position", CoverState.OPEN),
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
            State(
                "cover.tilt_partial_open_only_supports_tilt_position",
                CoverState.OPEN,
                {ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State(
                "cover.tilt_open_only_supports_tilt_position",
                CoverState.OPEN,
            ),
            State(
                "cover.tilt_closed_only_supports_tilt_position",
                CoverState.CLOSED,
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
            State(
                "cover.closed_supports_all_features",
                CoverState.CLOSED,
                {ATTR_CURRENT_POSITION: 0, ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State("cover.entity_close", CoverState.OPEN),
            State(
                "cover.closed_only_supports_close_open",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 100},
            ),
            State(
                "cover.open_only_supports_close_open",
                CoverState.CLOSED,
                {ATTR_CURRENT_POSITION: 50},
            ),
            State(
                "cover.open_only_supports_tilt_close_open",
                CoverState.CLOSED,
                {ATTR_CURRENT_TILT_POSITION: 50},
            ),
            State("cover.closed_only_supports_tilt_close_open", CoverState.OPEN),
            State("cover.open_missing_all_features", CoverState.CLOSED),
            State(
                "cover.closed_missing_all_features_has_position",
                CoverState.OPEN,
                {ATTR_CURRENT_POSITION: 70},
            ),
            State(
                "cover.open_missing_all_features_has_tilt_position",
                CoverState.OPEN,
                {ATTR_CURRENT_TILT_POSITION: 20},
            ),
            State("cover.closed_only_supports_position", CoverState.OPEN),
            State("cover.open_only_supports_position", CoverState.CLOSED),
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
            State(
                "cover.tilt_partial_open_only_supports_tilt_position",
                CoverState.OPEN,
                {ATTR_CURRENT_TILT_POSITION: 70},
            ),
            State(
                "cover.tilt_open_only_supports_tilt_position",
                CoverState.CLOSED,
            ),
            State(
                "cover.tilt_closed_only_supports_tilt_position",
                CoverState.OPEN,
            ),
        ],
    )

    valid_close_calls = [
        {"entity_id": "cover.entity_open"},
        {"entity_id": "cover.entity_open_attr"},
        {"entity_id": "cover.open_only_supports_close_open"},
        {"entity_id": "cover.open_missing_all_features"},
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
        {"entity_id": "cover.tilt_only_open"},
        {"entity_id": "cover.entity_open_attr"},
        {"entity_id": "cover.open_only_supports_tilt_close_open"},
    ]
    assert len(close_tilt_calls) == len(valid_close_tilt_calls)
    for call in close_tilt_calls:
        assert call.domain == "cover"
        assert call.data in valid_close_tilt_calls
        valid_close_tilt_calls.remove(call.data)

    valid_open_tilt_calls = [
        {"entity_id": "cover.tilt_only_closed"},
        {"entity_id": "cover.closed_only_supports_tilt_close_open"},
    ]
    assert len(open_tilt_calls) == len(valid_open_tilt_calls)
    for call in open_tilt_calls:
        assert call.domain == "cover"
        assert call.data in valid_open_tilt_calls
        valid_open_tilt_calls.remove(call.data)

    valid_position_calls = [
        {
            "entity_id": "cover.entity_close_attr",
            ATTR_POSITION: 50,
        },
        {
            "entity_id": "cover.closed_missing_all_features_has_position",
            ATTR_POSITION: 70,
        },
        {
            "entity_id": "cover.closed_only_supports_position",
            ATTR_POSITION: 100,
        },
        {
            "entity_id": "cover.open_only_supports_position",
            ATTR_POSITION: 0,
        },
        {
            "entity_id": "cover.closed_supports_all_features",
            ATTR_POSITION: 0,
        },
        {
            "entity_id": "cover.entity_entirely_open",
            ATTR_POSITION: 0,
        },
    ]
    assert len(position_calls) == len(valid_position_calls)
    for call in position_calls:
        assert call.domain == "cover"
        assert call.data in valid_position_calls
        valid_position_calls.remove(call.data)

    valid_position_tilt_calls = [
        {
            "entity_id": "cover.entity_close_attr",
            ATTR_TILT_POSITION: 50,
        },
        {
            "entity_id": "cover.open_missing_all_features_has_tilt_position",
            ATTR_TILT_POSITION: 20,
        },
        {
            "entity_id": "cover.tilt_open_only_supports_tilt_position",
            ATTR_TILT_POSITION: 0,
        },
        {
            "entity_id": "cover.tilt_closed_only_supports_tilt_position",
            ATTR_TILT_POSITION: 100,
        },
        {
            "entity_id": "cover.tilt_partial_open_only_supports_tilt_position",
            ATTR_TILT_POSITION: 70,
        },
        {
            "entity_id": "cover.closed_supports_all_features",
            ATTR_TILT_POSITION: 50,
        },
        {
            "entity_id": "cover.entity_close_tilt",
            ATTR_TILT_POSITION: 100,
        },
        {
            "entity_id": "cover.entity_open_tilt",
            ATTR_TILT_POSITION: 0,
        },
        {
            "entity_id": "cover.entity_entirely_open",
            ATTR_TILT_POSITION: 0,
        },
        {
            "entity_id": "cover.tilt_only_tilt_position_100",
            ATTR_TILT_POSITION: 0,
        },
        {
            "entity_id": "cover.tilt_only_tilt_position_0",
            ATTR_TILT_POSITION: 100,
        },
    ]
    for call in position_tilt_calls:
        if ATTR_TILT_POSITION not in call.data:
            continue
    assert len(position_tilt_calls) == len(valid_position_tilt_calls)
    for call in position_tilt_calls:
        assert call.domain == "cover"
        assert call.data in valid_position_tilt_calls
        valid_position_tilt_calls.remove(call.data)


OPEN_AT_50 = {
    CoverEntityCapabilityAttribute.OPEN_TILT_POSITION: 50,
    CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS: [0, 100],
}
OPEN_AT_0 = {
    CoverEntityCapabilityAttribute.OPEN_TILT_POSITION: 0,
    CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS: [100],
}


@pytest.mark.parametrize(
    (
        "current_state",
        "current_tilt",
        "tilt_attributes",
        "target_state",
        "expected_tilt_positions",
    ),
    [
        pytest.param(
            CoverState.CLOSED, 0, OPEN_AT_50, CoverState.OPEN, [50], id="open_at_50"
        ),
        pytest.param(
            CoverState.OPEN, 30, OPEN_AT_50, CoverState.CLOSED, [0], id="close_from_30"
        ),
        pytest.param(
            CoverState.OPEN, 100, OPEN_AT_50, CoverState.CLOSED, [], id="closed_at_100"
        ),
        pytest.param(
            CoverState.CLOSED, 100, OPEN_AT_0, CoverState.OPEN, [0], id="open_at_0"
        ),
        pytest.param(
            CoverState.OPEN, 0, OPEN_AT_0, CoverState.CLOSED, [100], id="close_at_100"
        ),
        pytest.param(
            CoverState.CLOSED, 0, {}, CoverState.OPEN, [100], id="default_open"
        ),
        pytest.param(
            CoverState.OPEN, 50, {}, CoverState.CLOSED, [0], id="default_close"
        ),
        pytest.param(
            CoverState.OPEN, 0, {}, CoverState.CLOSED, [0], id="default_closed_at_0"
        ),
        pytest.param(
            CoverState.OPENING,
            100,
            OPEN_AT_50,
            CoverState.CLOSED,
            [0],
            id="opening_from_100",
        ),
        pytest.param(
            CoverState.OPENING, 0, {}, CoverState.CLOSED, [0], id="opening_from_0"
        ),
        pytest.param(
            CoverState.CLOSING, 0, {}, CoverState.CLOSED, [0], id="closing_at_0"
        ),
    ],
)
async def test_reproducing_state_with_tilt_positions(
    hass: HomeAssistant,
    current_state: CoverState,
    current_tilt: int,
    tilt_attributes: dict[str, Any],
    target_state: CoverState,
    expected_tilt_positions: list[int],
) -> None:
    """Test a state without tilt uses the open and closed tilt positions."""
    hass.states.async_set(
        "cover.entity",
        current_state,
        {
            ATTR_CURRENT_TILT_POSITION: current_tilt,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_TILT_POSITION,
            **tilt_attributes,
        },
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_COVER_TILT_POSITION)

    await async_reproduce_state(hass, [State("cover.entity", target_state)])

    assert [call.data[ATTR_TILT_POSITION] for call in calls] == expected_tilt_positions


@pytest.mark.parametrize(
    ("current_state", "current_tilt", "tilt_attributes", "expected_calls"),
    [
        pytest.param(CoverState.OPEN, 30, OPEN_AT_50, 1, id="partly_open"),
        pytest.param(CoverState.OPEN, 100, OPEN_AT_50, 0, id="closed_at_100"),
        pytest.param(CoverState.OPEN, 0, OPEN_AT_50, 1, id="closed_at_0"),
        pytest.param(CoverState.OPEN, 0, {}, 1, id="default_closed_at_0"),
        pytest.param(CoverState.OPENING, 100, OPEN_AT_50, 1, id="opening_from_100"),
        pytest.param(CoverState.CLOSING, 100, OPEN_AT_50, 1, id="closing_at_100"),
        pytest.param(CoverState.OPENING, 0, {}, 1, id="opening_from_0"),
        pytest.param(CoverState.CLOSING, 0, {}, 1, id="closing_at_0"),
    ],
)
async def test_reproducing_closed_state_with_close_tilt(
    hass: HomeAssistant,
    current_state: CoverState,
    current_tilt: int,
    tilt_attributes: dict[str, Any],
    expected_calls: int,
) -> None:
    """Test closing leaves slats at another closed position where they are."""
    hass.states.async_set(
        "cover.entity",
        current_state,
        {
            ATTR_CURRENT_TILT_POSITION: current_tilt,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION,
            **tilt_attributes,
        },
    )
    calls = async_mock_service(hass, DOMAIN, SERVICE_CLOSE_COVER_TILT)

    await async_reproduce_state(hass, [State("cover.entity", CoverState.CLOSED)])

    assert len(calls) == expected_calls

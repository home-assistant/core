"""Tests for the Keyboard Remote click detector."""

from datetime import timedelta

import pytest

from homeassistant.components.keyboard_remote.click_detector import (
    ClickDetector,
    ClickType,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed_exact

UP = 0
DOWN = 1
ALL_TYPES = set(ClickType)
CLICK = ClickType.CLICK
DOUBLE_CLICK = ClickType.DOUBLE_CLICK
LONG_CLICK = ClickType.LONG_CLICK

# Past the double click timeout
TIMEOUT = 1.0


def _detector(
    hass: HomeAssistant, click_types: set[ClickType], fired: list[tuple[int, ClickType]]
) -> ClickDetector:
    return ClickDetector(
        hass.loop,
        lambda code, click_type: fired.append((code, click_type)),
        click_types,
        click_threshold=0.4,
        double_click_timeout=0.3,
        long_click_max=3.0,
    )


async def _wait(hass: HomeAssistant, seconds: float) -> None:
    """Fire the timers due within the given time, without the usual 0.5 s bump."""
    async_fire_time_changed_exact(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("click_types", "events", "expected"),
    [
        pytest.param(
            ALL_TYPES,
            [(30, DOWN, 0.0, 0), (30, UP, 0.1, TIMEOUT)],
            [(30, CLICK)],
            id="click_after_double_click_timeout",
        ),
        pytest.param(
            ALL_TYPES,
            [(30, DOWN, 0.0, 0), (30, UP, 0.1, 0)],
            [],
            id="click_waits_for_double_click",
        ),
        pytest.param(
            {CLICK, LONG_CLICK},
            [(30, DOWN, 0.0, 0), (30, UP, 0.1, 0)],
            [(30, CLICK)],
            id="click_immediate_without_double_click",
        ),
        pytest.param(
            ALL_TYPES,
            [
                (30, DOWN, 0.0, 0),
                (30, UP, 0.1, 0),
                (30, DOWN, 0.2, 0),
                (30, UP, 0.3, TIMEOUT),
            ],
            [(30, DOUBLE_CLICK)],
            id="double_click",
        ),
        pytest.param(
            ALL_TYPES,
            [
                (30, DOWN, 0.0, 0),
                (30, UP, 0.1, 0),
                (30, DOWN, 0.2, 0),
                (30, UP, 5.0, TIMEOUT),
            ],
            [(30, DOUBLE_CLICK)],
            id="double_click_with_long_second_press",
        ),
        pytest.param(
            ALL_TYPES,
            [
                (30, DOWN, 0.0, 0),
                (30, UP, 0.1, TIMEOUT),
                (30, DOWN, 2.0, 0),
                (30, UP, 2.1, TIMEOUT),
            ],
            [(30, CLICK), (30, CLICK)],
            id="second_press_after_timeout_is_a_click",
        ),
        pytest.param(
            {CLICK},
            [
                (30, DOWN, 0.0, 0),
                (30, UP, 0.1, 0),
                (30, DOWN, 0.2, 0),
                (30, UP, 0.3, 0),
            ],
            [(30, CLICK), (30, CLICK)],
            id="quick_presses_are_clicks_without_double_click",
        ),
        pytest.param(
            ALL_TYPES,
            [(30, DOWN, 0.0, 0), (30, UP, 1.0, 0)],
            [(30, LONG_CLICK)],
            id="long_click",
        ),
        pytest.param(
            ALL_TYPES,
            [(30, DOWN, 0.0, 0), (30, UP, 0.4, 0)],
            [(30, LONG_CLICK)],
            id="long_click_at_click_threshold",
        ),
        pytest.param(
            ALL_TYPES,
            [(30, DOWN, 0.0, 0), (30, UP, 3.0, 0)],
            [(30, LONG_CLICK)],
            id="long_click_at_maximum",
        ),
        pytest.param(
            ALL_TYPES,
            [(30, DOWN, 0.0, 0), (30, UP, 3.5, TIMEOUT)],
            [],
            id="held_past_long_click_maximum",
        ),
        pytest.param(
            {DOUBLE_CLICK, LONG_CLICK},
            [(30, DOWN, 0.0, 0), (30, UP, 0.1, TIMEOUT)],
            [],
            id="click_not_selected",
        ),
        pytest.param(
            {CLICK, DOUBLE_CLICK},
            [(30, DOWN, 0.0, 0), (30, UP, 1.0, TIMEOUT)],
            [],
            id="long_click_not_selected",
        ),
        pytest.param(
            ALL_TYPES,
            [(30, UP, 0.1, TIMEOUT)],
            [],
            id="key_up_without_key_down",
        ),
        pytest.param(
            ALL_TYPES,
            [(30, DOWN, 0.0, 0), (30, DOWN, 5.0, 0), (30, UP, 5.1, TIMEOUT)],
            [(30, CLICK)],
            id="lost_key_up_restarts_the_press",
        ),
        pytest.param(
            ALL_TYPES,
            [
                (30, DOWN, 0.0, 0),
                (31, DOWN, 0.1, 0),
                (30, UP, 0.2, 0),
                (31, UP, 1.2, TIMEOUT),
            ],
            [(31, LONG_CLICK), (30, CLICK)],
            id="keys_are_independent",
        ),
    ],
)
async def test_click_detection(
    hass: HomeAssistant,
    click_types: set[ClickType],
    events: list[tuple[int, int, float, float]],
    expected: list[tuple[int, ClickType]],
) -> None:
    """Test key presses fire the selected click types.

    Each event is a key code, key value and event timestamp, followed by how
    long to let timers run after it.
    """
    fired: list[tuple[int, ClickType]] = []
    detector = _detector(hass, click_types, fired)

    for code, value, timestamp, wait in events:
        (detector.key_up, detector.key_down)[value](code, timestamp)
        await _wait(hass, wait)

    assert fired == expected


async def test_cancel_drops_pending_click(hass: HomeAssistant) -> None:
    """Test a click waiting for a possible double click is dropped on cancel."""
    fired: list[tuple[int, ClickType]] = []
    detector = _detector(hass, ALL_TYPES, fired)

    detector.key_down(30, 0.0)
    detector.key_up(30, 0.1)
    detector.cancel()
    await _wait(hass, TIMEOUT)

    assert fired == []

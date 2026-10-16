"""Detect clicks, double clicks and long clicks from key press timing."""

import asyncio
from collections.abc import Callable
from enum import StrEnum

from homeassistant.core import callback


class ClickType(StrEnum):
    """A key event derived from how long and how often a key is pressed."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    LONG_CLICK = "long_click"


class _KeyState:
    """Press tracking for one key code."""

    __slots__ = ("double_click_timer", "pressed_at", "second_press")

    def __init__(self) -> None:
        """Initialize an idle key."""
        # Event timestamp of the key_down, None while released
        self.pressed_at: float | None = None
        # Pressed again while waiting for a double click
        self.second_press = False
        self.double_click_timer: asyncio.TimerHandle | None = None


class ClickDetector:
    """Turn key_down and key_up events of one device into click events.

    A press shorter than the click threshold is a click, and one held up to
    the long click maximum is a long click. Holding longer fires nothing. When
    double clicks are enabled, a click only fires once the double click
    timeout passes without a second press, and a second press within it fires
    a double click instead. Each press fires at most one of these.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        fire: Callable[[int, ClickType], None],
        click_types: set[ClickType],
        *,
        click_threshold: float,
        double_click_timeout: float,
        long_click_max: float,
    ) -> None:
        """Initialize the detector."""
        self._loop = loop
        self._fire = fire
        self._click_types = click_types
        self._click_threshold = click_threshold
        self._double_click_timeout = double_click_timeout
        self._long_click_max = long_click_max
        self._keys: dict[int, _KeyState] = {}

    @callback
    def key_down(self, code: int, timestamp: float) -> None:
        """Handle a key press at the event's timestamp."""
        state = self._keys.setdefault(code, _KeyState())
        # A key_down with no key_up before it, as when one was lost, starts a
        # new first press
        state.second_press = state.double_click_timer is not None
        if state.double_click_timer is not None:
            state.double_click_timer.cancel()
            state.double_click_timer = None
        state.pressed_at = timestamp

    @callback
    def key_up(self, code: int, timestamp: float) -> None:
        """Handle a key release at the event's timestamp."""
        if (state := self._keys.get(code)) is None or state.pressed_at is None:
            return
        held = timestamp - state.pressed_at
        state.pressed_at = None
        if state.second_press:
            state.second_press = False
            self._async_fire(code, ClickType.DOUBLE_CLICK)
        elif held < self._click_threshold:
            if ClickType.DOUBLE_CLICK in self._click_types:
                state.double_click_timer = self._loop.call_later(
                    self._double_click_timeout, self._async_click_timed_out, code
                )
            else:
                self._async_fire(code, ClickType.CLICK)
        elif held <= self._long_click_max:
            self._async_fire(code, ClickType.LONG_CLICK)

    @callback
    def cancel(self) -> None:
        """Drop pending clicks, so none fires after the device is released."""
        for state in self._keys.values():
            if state.double_click_timer is not None:
                state.double_click_timer.cancel()
        self._keys.clear()

    @callback
    def _async_click_timed_out(self, code: int) -> None:
        """Fire the click no second press followed."""
        self._keys[code].double_click_timer = None
        self._async_fire(code, ClickType.CLICK)

    @callback
    def _async_fire(self, code: int, click_type: ClickType) -> None:
        if click_type in self._click_types:
            self._fire(code, click_type)

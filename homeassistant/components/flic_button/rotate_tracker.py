"""Rotation tracking for Flic Twist buttons."""

from collections import deque
from dataclasses import dataclass
import time

UNITS_PER_SLICE = 4096  # 12 slices per revolution
D360 = 12 * UNITS_PER_SLICE  # 49152
D120 = D360 // 3  # 16384 - third rotation (120 degrees)
D90 = D360 // 4  # 12288 - quarter rotation (90 degrees)


@dataclass
class RotateResult:
    """Result of a rotation update."""

    angle_degrees: float  # 0..360
    selector_index: int  # 0..11
    total_turns: float  # accumulated revolutions (+/-)
    detent_crossings: int  # number of 4096-boundaries crossed this packet (+/-)
    current_detent_crossings: int
    acceleration_multiplier: float  # 1.0 - 100.0, increases with faster rotation
    rpm: float  # revolutions per minute (positive = clockwise, negative = counter-clockwise)
    backlash_suppressed: bool = False  # True if this delta was filtered as noise


class RotateTracker:
    """Track rotational position and velocity for Flic Twist buttons."""

    # Backlash suppression: accumulated reverse movement required before accepting
    # a direction change. Small reverse deltas are buffered; forward deltas cancel
    # the buffer. The net position stays accurate because buffered movement is
    # applied in full once the threshold is reached.
    BACKLASH_DELTA_THRESHOLD = (
        1500  # units - minimum reverse to accept direction change
    )

    def __init__(
        self,
        *,
        enable_backlash_suppression: bool = False,
        full_range_units: int = D360,
        clamp_position: bool = False,
    ) -> None:
        """Initialize the rotation tracker.

        Args:
            enable_backlash_suppression: If True, filter out spurious direction
                changes when releasing after rotation. Useful for Duo devices
                which have mechanical backlash.
            full_range_units: Units for full range (100%). Default is D360 (360°).
                Use D120 (120°) for Duo dial behavior.
            clamp_position: If True, clamp accumulated units to 0-full_range_units.

        """
        self._acc_units: int = 0  # running total in "units"
        self._current_detent_crossings: int = 0
        self._last_timestamp: float = 0.0
        self._last_velocity: float = 0.0
        self._velocity_history: deque[float] = deque(maxlen=5)
        self._current_direction: int = 0  # 1=CW, -1=CCW, 0=unknown
        self._reverse_buffer: int = 0  # accumulated reverse movement pending commit
        self._enable_backlash_suppression = enable_backlash_suppression
        self._full_range_units = full_range_units
        self._clamp_position = clamp_position

    @property
    def accumulated_units(self) -> int:
        """Return the accumulated units (raw position)."""
        return self._acc_units

    def clamp_accumulated_units(self, min_units: int, max_units: int) -> None:
        """Clamp accumulated units to a range.

        Args:
            min_units: Minimum allowed value
            max_units: Maximum allowed value

        """
        self._acc_units = max(min_units, min(max_units, self._acc_units))

    @property
    def percentage(self) -> float:
        """Return current position as percentage (0-100) of full range.

        The percentage is based on the configured full_range_units:
        - For Twist (D360): 360° rotation = 100%
        - For Duo (D120): 120° rotation = 100%

        Returns:
            Position as percentage (0.0-100.0), clamped if clamp_position is True.

        """
        raw_pct = (self._acc_units / self._full_range_units) * 100.0
        if self._clamp_position:
            return max(0.0, min(100.0, raw_pct))
        return raw_pct

    def apply(self, delta: int) -> RotateResult:
        """Apply a rotation delta and return the new state.

        When backlash suppression is enabled, reverse deltas are buffered
        instead of applied immediately. Forward deltas cancel the buffer
        (preserving net accuracy). A direction change is only committed
        when the buffered reverse movement exceeds BACKLASH_DELTA_THRESHOLD.
        """
        # Calculate timestamp and velocity
        current_timestamp = time.monotonic() * 1000  # Convert to milliseconds
        if self._last_timestamp > 0:
            time_delta = current_timestamp - self._last_timestamp
        else:
            time_delta = 1.0  # avoid division by zero on first packet

        # Calculate instantaneous velocity
        if time_delta > 0:
            instant_velocity = delta / time_delta
        else:
            instant_velocity = 0.0

        # Backlash suppression using reverse-buffer hysteresis
        suppress_for_backlash = False
        prev = self._acc_units

        if self._enable_backlash_suppression and self._current_direction != 0:
            is_forward = (delta > 0) == (self._current_direction > 0)

            if is_forward and self._reverse_buffer == 0:
                # Moving forward with no pending buffer — apply directly
                self._acc_units += delta
            else:
                # Either a reverse delta or there's pending buffer to resolve.
                # Net the delta against the buffer to preserve position accuracy.
                self._reverse_buffer += delta

                if self._reverse_buffer == 0:
                    # Buffer perfectly cancelled — noise absorbed
                    suppress_for_backlash = True
                elif (self._reverse_buffer > 0) == (self._current_direction > 0):
                    # Buffer swung back to forward — apply and clear
                    self._acc_units += self._reverse_buffer
                    self._reverse_buffer = 0
                elif abs(self._reverse_buffer) >= self.BACKLASH_DELTA_THRESHOLD:
                    # Enough reverse accumulated — genuine direction change
                    self._acc_units += self._reverse_buffer
                    self._current_direction = 1 if self._reverse_buffer > 0 else -1
                    self._reverse_buffer = 0
                else:
                    # Reverse below threshold — hold in buffer
                    suppress_for_backlash = True
        else:
            # No backlash suppression or no established direction — apply directly
            self._acc_units += delta
            if delta != 0:
                self._current_direction = 1 if delta > 0 else -1

        # Clamp position if configured (for Duo dial mode)
        if self._clamp_position:
            self._acc_units = max(0, min(self._full_range_units, self._acc_units))

        # Calculate detent crossings
        raw_detent_crossings = self._detent_crossings_between(prev, self._acc_units)
        detent_crossings = 0 if suppress_for_backlash else raw_detent_crossings
        self._current_detent_crossings += detent_crossings

        units_mod = self._floor_mod(self._acc_units, D360)
        angle_deg = units_mod * 360.0 / D360
        selector_index = units_mod // UNITS_PER_SLICE

        # Add to history (maxlen handles window size automatically)
        self._velocity_history.append(instant_velocity)

        # Calculate smoothed velocity using moving average
        if self._velocity_history:
            current_velocity = sum(self._velocity_history) / len(self._velocity_history)
        else:
            current_velocity = 0.0

        # Use absolute velocity as basis for multiplier (fast spinning = higher multiplier)
        abs_velocity = abs(current_velocity)

        # Calculate RPM (revolutions per minute)
        # current_velocity is in units/millisecond
        # Convert to revolutions/minute: (units/ms) * (1 rev / D360 units) * (60000 ms / 1 min)
        rpm = (current_velocity / D360) * 60000.0

        # Map velocity to multiplier range 1.0 - 100.0 with exponential curve
        # This gives better slow speed detection (stays at 1.0 longer)
        velocity_threshold = 10.0  # velocity below this stays near 1.0
        velocity_max = 100.0  # velocity at which we reach 100.0
        if abs_velocity < velocity_threshold:
            acceleration_multiplier = 1.0
        else:
            acceleration_multiplier = min(
                100.0,
                max(
                    1.0,
                    1.0
                    + (
                        (abs_velocity - velocity_threshold)
                        / (velocity_max - velocity_threshold)
                    )
                    * 99.0,
                ),
            )

        self._last_timestamp = current_timestamp
        self._last_velocity = current_velocity

        return RotateResult(
            angle_degrees=angle_deg,
            selector_index=selector_index,  # 0..11
            total_turns=self._acc_units / D360,
            detent_crossings=detent_crossings,
            current_detent_crossings=self._current_detent_crossings,
            acceleration_multiplier=acceleration_multiplier,
            rpm=rpm,
            backlash_suppressed=suppress_for_backlash,
        )

    def _detent_crossings_between(self, a: int, b: int) -> int:
        """Count detent boundaries crossed between two positions.

        Uses the unbounded accumulator; returns positive for forward, negative for backward.
        """
        if a == b:
            return 0
        step = UNITS_PER_SLICE // 2
        lo = min(a, b)
        hi = max(a, b)
        k_lo = self._floor_div(lo, step)
        k_hi = self._floor_div(hi, step)
        crossings = k_hi - k_lo
        return crossings if a <= b else -crossings

    def _floor_div(self, a: int, b: int) -> int:
        """Floor division that handles negative numbers correctly."""
        q = a // b
        r = a % b
        if r != 0 and (a < 0) != (b < 0):
            q -= 1
        return q

    def _floor_mod(self, a: int, m: int) -> int:
        """Floor modulo that always returns a non-negative result."""
        r = a % m
        return r if r >= 0 else r + m


class MultiModeRotateTracker:
    """Track rotation for all 13 Twist modes independently.

    Each Flic Twist has 13 modes:
    - Modes 0-11: Individual slot positions (each tracks 0-360 degrees)
    - Mode 12: Push-twist mode (rotation selects which slot 0-11 is active)
    """

    def __init__(self) -> None:
        """Initialize trackers for all 13 modes."""
        self._trackers: list[RotateTracker] = [RotateTracker() for _ in range(13)]
        self._received_packet_count: int = 0

    def apply(self, mode_index: int, delta: int) -> RotateResult:
        """Apply rotation delta to specific mode tracker.

        For slot modes (0-11), the accumulated units are clamped to 0-D360
        so the position stays within 0-100% and doesn't require excessive
        rotation to return from the limits.

        Args:
            mode_index: The twist mode index (0-12)
            delta: Rotation delta in units

        Returns:
            RotateResult with updated state for this mode

        """
        self._received_packet_count += 1
        if 0 <= mode_index < 13:
            tracker = self._trackers[mode_index]
            result = tracker.apply(delta)
            # Clamp slot modes (0-11) to 0-D360 range (0-100%)
            # Mode 12 (push-twist selector) is not clamped
            if mode_index < 12:
                tracker.clamp_accumulated_units(0, D360)
            return result
        # Fallback to mode 0 for out-of-range indices
        return self._trackers[0].apply(delta)

    def get_mode_percentage(self, mode_index: int) -> float:
        """Get current position as 0-100% for a mode, clamped.

        For slot modes (0-11), the percentage is clamped between 0 and 100
        rather than wrapping around. This means rotating past 100% stays at 100%,
        and rotating below 0% stays at 0%.

        Args:
            mode_index: The twist mode index (0-12)

        Returns:
            Position as percentage (0.0-100.0), clamped

        """
        if 0 <= mode_index < 13:
            tracker = self._trackers[mode_index]
            # Use accumulated units and clamp to 0-100% range
            # D360 units = one full rotation = 100%
            raw_percentage = (tracker.accumulated_units / D360) * 100.0
            return max(0.0, min(100.0, raw_percentage))
        return 0.0

    def get_mode_position(self, mode_index: int) -> int:
        """Get raw accumulated units for a mode.

        Used for UpdateTwistPosInd to sync host state with device.

        Args:
            mode_index: The twist mode index (0-12)

        Returns:
            Raw accumulated units value

        """
        if 0 <= mode_index < 13:
            return self._trackers[mode_index].accumulated_units
        return 0

    @property
    def received_packet_count(self) -> int:
        """Return total number of received rotation packets."""
        return self._received_packet_count

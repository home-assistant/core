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
    detent_crossings: int  # number of percentage-boundaries crossed this packet (+/-)
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

    def set_accumulated_units(self, units: int) -> None:
        """Set the accumulated units directly.

        Resets direction and backlash buffer since the position is being
        externally overridden.

        Args:
            units: New raw position in units

        """
        self._acc_units = units
        self._current_direction = 0
        self._reverse_buffer = 0

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

        # Compute integer percentage before and after to detect 1% increments.
        # Use unclamped position so events fire even when clamped at 0/100%.
        prev_pct = (prev * 100) // self._full_range_units
        new_pct = (self._acc_units * 100) // self._full_range_units

        # Clamp position if configured (for Duo dial mode)
        if self._clamp_position:
            self._acc_units = max(0, min(self._full_range_units, self._acc_units))

        raw_detent_crossings = new_pct - prev_pct
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

    def _floor_mod(self, a: int, m: int) -> int:
        """Floor modulo that always returns a non-negative result."""
        r = a % m
        return r if r >= 0 else r + m


class MultiModeRotateTracker:
    """Track rotation for all 13 Twist modes independently.

    Mirrors the SDK's position/min model:
    - position: absolute accumulated rotation (unbounded)
    - min: lower boundary, adjusted from min_delta/max_delta in notifications
    - bounded_position = position - min (always in [0, D360])

    Each Flic Twist has 13 modes:
    - Modes 0-11: Individual slot positions (bounded to 0-D360)
    - Mode 12: Slot-changing mode (free rotation to select active slot)
    """

    def __init__(self) -> None:
        """Initialize trackers for all 13 modes."""
        self._trackers: list[RotateTracker] = [RotateTracker() for _ in range(13)]
        self._positions: list[int] = [0] * 13  # absolute position per mode
        self._mins: list[int] = [0] * 13  # min boundary per mode
        self._received_packet_count: int = 0

    def apply(
        self,
        mode_index: int,
        total_delta: int,
        min_delta: int = 0,
        max_delta: int = 0,
        last_min_update_was_top: bool = False,
    ) -> RotateResult:
        """Apply rotation delta using the SDK's position/min tracking.

        Args:
            mode_index: The twist mode index (0-12)
            total_delta: Total rotation delta from TwistEventNotification
            min_delta: Minimum intermediate delta (for min boundary updates)
            max_delta: Maximum intermediate delta (for min boundary updates)
            last_min_update_was_top: Controls order of boundary checks

        Returns:
            RotateResult with updated state for this mode

        """
        self._received_packet_count += 1
        if not 0 <= mode_index < 13:
            mode_index = 0

        # Update absolute position (unbounded)
        new_position = self._positions[mode_index] + total_delta

        # Update min boundary for slot modes (0-11) using SDK logic
        current_min = self._mins[mode_index]
        if mode_index < 12:
            bottom = new_position - min_delta
            top = new_position - max_delta

            if last_min_update_was_top:
                current_min = min(current_min, bottom)
                if top > current_min + D360:
                    current_min = top - D360
            else:
                if top > current_min + D360:
                    current_min = top - D360
                current_min = min(current_min, bottom)

            # Final bounds check
            if new_position < current_min:
                current_min = new_position
            elif new_position > current_min + D360:
                current_min = new_position - D360

            self._mins[mode_index] = current_min

        self._positions[mode_index] = new_position

        # Compute bounded position (display value)
        bounded = new_position - self._mins[mode_index]

        # Use bounded delta for RotateTracker (detent crossings, velocity)
        tracker = self._trackers[mode_index]
        old_acc = tracker.accumulated_units
        bounded_delta = bounded - old_acc
        result = tracker.apply(bounded_delta)
        # Keep tracker in sync with bounded position
        if tracker.accumulated_units != bounded:
            tracker.set_accumulated_units(bounded)

        return result

    def get_mode_percentage(self, mode_index: int) -> float:
        """Get bounded position as 0-100% for a mode.

        Args:
            mode_index: The twist mode index (0-12)

        Returns:
            Position as percentage (0.0-100.0), clamped

        """
        if 0 <= mode_index < 13:
            bounded = self._positions[mode_index] - self._mins[mode_index]
            raw_percentage = (bounded / D360) * 100.0
            return max(0.0, min(100.0, raw_percentage))
        return 0.0

    def get_absolute_position(self, mode_index: int) -> int:
        """Get absolute (unbounded) position for a mode.

        Used to compute new_min in UpdateTwistPositionRequest.

        Args:
            mode_index: The twist mode index (0-12)

        Returns:
            Absolute accumulated position value

        """
        if 0 <= mode_index < 13:
            return self._positions[mode_index]
        return 0

    def set_mode_min(self, mode_index: int, new_min: int) -> None:
        """Set min boundary for a mode.

        Called after sending UpdateTwistPositionRequest to keep local
        state in sync with the device.

        Args:
            mode_index: The twist mode index (0-12)
            new_min: New min boundary value

        """
        if 0 <= mode_index < 13:
            self._mins[mode_index] = new_min
            # Update tracker to match new bounded position
            bounded = self._positions[mode_index] - new_min
            self._trackers[mode_index].set_accumulated_units(bounded)

    @property
    def received_packet_count(self) -> int:
        """Return total number of received rotation packets."""
        return self._received_packet_count

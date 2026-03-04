"""Test the Flic Button rotate tracker."""

from homeassistant.components.flic_button.rotate_tracker import (
    D360,
    MultiModeRotateTracker,
)


def test_multi_mode_tracker_mode_12_unbounded_by_default() -> None:
    """Test mode 12 does not track min boundary when bound_mode_12 is False.

    Without bounding, the absolute position grows without min adjusting,
    so reversing from 2*D360 requires a full 2*D360 reverse to reach 0%.
    """
    tracker = MultiModeRotateTracker()

    # Rotate mode 12 by two full revolutions
    tracker.apply(12, D360)
    tracker.apply(12, D360)
    pct = tracker.get_mode_percentage(12)
    # Clamped to 100% by get_mode_percentage
    assert pct == 100.0

    # Reverse one revolution — without bounding, position = D360, min = 0
    # bounded = D360 → 100%, not 0% as it would be with bounding
    tracker.apply(12, -D360)
    pct = tracker.get_mode_percentage(12)
    assert pct == 100.0


def test_multi_mode_tracker_mode_12_bounded() -> None:
    """Test mode 12 is bounded (0-100%) when bound_mode_12 is True."""
    tracker = MultiModeRotateTracker(bound_mode_12=True)

    # Rotate mode 12 by a full revolution
    tracker.apply(12, D360)
    pct = tracker.get_mode_percentage(12)
    assert pct == 100.0

    # Rotate further — should stay at 100% because min tracks
    tracker.apply(12, D360)
    pct = tracker.get_mode_percentage(12)
    assert pct == 100.0


def test_multi_mode_tracker_mode_12_bounded_reverse() -> None:
    """Test bounded mode 12 tracks back to 0% on reverse rotation."""
    tracker = MultiModeRotateTracker(bound_mode_12=True)

    # Move to 50%
    half_rev = D360 // 2
    tracker.apply(12, half_rev)
    pct = tracker.get_mode_percentage(12)
    assert 49.0 <= pct <= 51.0

    # Reverse back to 0
    tracker.apply(12, -half_rev)
    pct = tracker.get_mode_percentage(12)
    assert pct == 0.0


def test_multi_mode_tracker_slot_modes_always_bounded() -> None:
    """Test slot modes (0-11) are always bounded regardless of bound_mode_12."""
    for bound_mode_12 in (True, False):
        tracker = MultiModeRotateTracker(bound_mode_12=bound_mode_12)

        # Rotate slot 0 by a full revolution
        tracker.apply(0, D360)
        pct = tracker.get_mode_percentage(0)
        assert pct == 100.0

        # Rotate further — should stay at 100% (bounded)
        tracker.apply(0, D360)
        pct = tracker.get_mode_percentage(0)
        assert pct == 100.0

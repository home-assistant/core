#!/usr/bin/env python3
"""Test sensor mapping functionality."""

import pytest
from span_panel_api.phase_validation import are_tabs_opposite_phase, get_tab_phase


def test_tab_phase_determination() -> None:
    """Test that tab phases are determined correctly."""
    # Test some known phase assignments
    assert get_tab_phase(1) == "L1"  # Left side, position 0
    assert get_tab_phase(2) == "L1"  # Right side, position 0
    assert get_tab_phase(3) == "L2"  # Left side, position 1
    assert get_tab_phase(4) == "L2"  # Right side, position 1
    assert get_tab_phase(5) == "L1"  # Left side, position 2
    assert get_tab_phase(6) == "L1"  # Right side, position 2


def test_opposite_phase_validation() -> None:
    """Test that opposite phase validation works correctly."""
    # Test opposite phase combinations (should be valid)
    assert are_tabs_opposite_phase(1, 3) is True  # L1 + L2
    assert are_tabs_opposite_phase(2, 4) is True  # L1 + L2
    assert are_tabs_opposite_phase(1, 4) is True  # L1 + L2
    assert are_tabs_opposite_phase(3, 6) is True  # L2 + L1

    # Test same phase combinations (should be invalid)
    assert are_tabs_opposite_phase(1, 2) is False  # L1 + L1
    assert are_tabs_opposite_phase(3, 4) is False  # L2 + L2
    assert are_tabs_opposite_phase(1, 5) is False  # L1 + L1
    assert are_tabs_opposite_phase(2, 6) is False  # L1 + L1


if __name__ == "__main__":
    pytest.main([__file__])

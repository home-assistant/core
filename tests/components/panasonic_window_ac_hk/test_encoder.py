"""Tests for the Panasonic Window A/C infrared encoder."""

import pytest

from homeassistant.components.panasonic_window_ac_hk import encoder


def test_build_short_frame_rejects_unknown_kind() -> None:
    """Test an unknown short-frame kind raises a descriptive ValueError."""
    with pytest.raises(ValueError, match="unknown short-frame kind: 'bogus'"):
        encoder.build_short_frame("bogus")

"""Test ScorpionTrack helper utilities."""

from __future__ import annotations

from homeassistant.components.scorpiontrack.utils import mask_token


def test_mask_token_handles_empty_and_short_values() -> None:
    """Token masking should handle empty and short values safely."""
    assert mask_token("   ") == "<empty>"
    assert mask_token("abcd") == "****"

"""Test ScorpionTrack helper utilities."""

from homeassistant.components.scorpiontrack.utils import mask_token


def test_mask_token_handles_empty_and_short_values() -> None:
    """Token masking should handle empty and short values safely."""
    assert mask_token("   ") == "<empty>"
    assert mask_token("abcd") == "****"


def test_mask_token_clamps_visible_characters() -> None:
    """Token masking should not leak the token if visible is too small."""
    assert mask_token("abcdef", visible=0) == "a...f"
    assert mask_token("abcdef", visible=-1) == "a...f"

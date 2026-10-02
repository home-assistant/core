"""Tests for the Mistral API helpers."""

from mistralai.client.types import UNSET

from homeassistant.components.mistral_ai.api import is_unset


def test_is_unset() -> None:
    """UNSET sentinel detection."""
    assert is_unset(UNSET)
    assert not is_unset(None)
    assert not is_unset("x")

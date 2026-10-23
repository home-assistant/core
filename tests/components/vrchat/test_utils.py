"""Test Home Assistant presentation helpers."""

from homeassistant.components.vrchat.utils import normalize_vrchat_enum_value


def test_normalize_vrchat_values() -> None:
    """Test enum normalization."""
    assert normalize_vrchat_enum_value("active on web") == "active_on_web"
    assert normalize_vrchat_enum_value("") is None

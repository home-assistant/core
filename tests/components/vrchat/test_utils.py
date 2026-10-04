"""Test Home Assistant presentation helpers."""

from homeassistant.components.vrchat.utils import (
    normalize_vrchat_enum_value,
    svg_file_uri,
)


def test_normalize_and_encode_vrchat_values() -> None:
    """Test enum normalization and SVG data URI encoding."""
    assert normalize_vrchat_enum_value("active on web") == "active_on_web"
    assert normalize_vrchat_enum_value("") is None
    assert svg_file_uri("<svg />").startswith(
        "data:image/svg+xml;charset=utf-8;base64,"
    )

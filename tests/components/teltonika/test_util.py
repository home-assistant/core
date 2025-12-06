"""Test Teltonika utility helpers."""

from homeassistant.components.teltonika.util import get_url_variants, normalize_url


def test_normalize_url_adds_https_scheme() -> None:
    """Test normalize_url adds HTTPS scheme for bare hostnames."""
    assert normalize_url("teltonika") == "https://teltonika"


def test_normalize_url_preserves_scheme() -> None:
    """Test normalize_url preserves explicitly provided scheme."""
    assert normalize_url("http://teltonika") == "http://teltonika"
    assert normalize_url("https://teltonika") == "https://teltonika"


def test_normalize_url_strips_path() -> None:
    """Test normalize_url removes any path component."""
    assert normalize_url("https://teltonika/api") == "https://teltonika"
    assert normalize_url("http://teltonika/other/path") == "http://teltonika"


def test_get_url_variants_with_https_scheme() -> None:
    """Test get_url_variants with explicit HTTPS scheme returns only HTTPS."""
    assert get_url_variants("https://teltonika") == ["https://teltonika"]


def test_get_url_variants_with_http_scheme() -> None:
    """Test get_url_variants with explicit HTTP scheme returns only HTTP."""
    assert get_url_variants("http://teltonika") == ["http://teltonika"]


def test_get_url_variants_without_scheme() -> None:
    """Test get_url_variants without scheme returns both HTTPS and HTTP."""
    assert get_url_variants("teltonika") == [
        "https://teltonika",
        "http://teltonika",
    ]

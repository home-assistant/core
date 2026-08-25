"""Tests for the HTTP configuration helpers."""

from homeassistant.components.http.config import update_url_port


def test_update_url_port_updates_explicit_old_port() -> None:
    """Update a URL that explicitly uses the previous server port."""
    assert update_url_port("http://homeassistant.local:8123", 8123, 9123) == (
        "http://homeassistant.local:9123"
    )


def test_update_url_port_preserves_other_ports() -> None:
    """Preserve URLs that point at a reverse proxy on another port."""
    url = "https://proxy.example:8443"
    assert update_url_port(url, 8123, 9123) == url


def test_update_url_port_preserves_url_without_explicit_port() -> None:
    """Do not add a port to a URL that did not explicitly contain one."""
    url = "http://homeassistant.local"
    assert update_url_port(url, 80, 9123) == url

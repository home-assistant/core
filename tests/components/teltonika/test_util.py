"""Test Teltonika utility helpers."""

from homeassistant.components.teltonika.util import API_SUFFIX, candidate_base_urls


def test_candidate_base_urls_preserves_hostname_with_scheme() -> None:
    """Ensure hostnames with scheme are preserved when adding the API suffix."""

    assert candidate_base_urls("https://teltonika") == [
        f"https://teltonika{API_SUFFIX}",
        f"http://teltonika{API_SUFFIX}",
    ]


def test_candidate_base_urls_preserves_hostname_without_scheme() -> None:
    """Ensure hostnames without scheme are preserved when adding the API suffix."""

    host = "teltonikap"
    assert candidate_base_urls(host) == [
        f"https://{host}{API_SUFFIX}",
        f"http://{host}{API_SUFFIX}",
    ]


def test_candidate_base_urls_strips_api_suffix_once() -> None:
    """Ensure only the trailing API suffix is removed from hostnames."""

    assert candidate_base_urls("http://teltonika/api") == [
        f"http://teltonika{API_SUFFIX}",
        f"https://teltonika{API_SUFFIX}",
    ]

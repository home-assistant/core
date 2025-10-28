"""Utilities for the eGauge integration."""


def _build_client_url(host: str, use_ssl: bool) -> str:
    """Builds the base URL for EgaugeJsonClient."""
    protocol = "https://" if use_ssl else "http://"
    return protocol + host

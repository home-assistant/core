"""Helpers for the Open Responses integration."""


def client_base_url(base_url: str) -> str:
    """Return the provider root URL passed to openresponses-python."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized

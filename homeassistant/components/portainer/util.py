"""Utility functions for the Portainer integration."""


def sanitize_container_name(container_name: str) -> str:
    """Sanitize to get a proper container name."""
    return container_name.replace("/", " ").strip()

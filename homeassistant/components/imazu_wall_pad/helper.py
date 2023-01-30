"""Helper methods for common Wall Pad integration operations."""


def format_host(host: str) -> str:
    """Format the host address string for entry into dev reg."""
    return host.replace(".", "_")


def host_to_last(host: str) -> str:
    """Format the host simple address string for entry into dev reg."""
    return host.split(".")[3]

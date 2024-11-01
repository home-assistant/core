"""Support for Lutron Homeworks Series 4 and 8 systems."""


def calculate_unique_id(controller_id: str, addr: str, idx: int) -> str:
    """Calculate entity unique id."""
    return f"homeworks.{controller_id}.{addr}.{idx}"

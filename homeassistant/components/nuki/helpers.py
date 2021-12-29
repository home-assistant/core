"""nuki integration helpers."""


def parse_id(hardware_id):
    """Parse Nuki ID."""
    return hex(hardware_id).split("x")[-1].upper()

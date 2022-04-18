"""Helpers to generate ulids."""


from ulid import ULID


def ulid_hex() -> str:
    """Generate a ulid in hex."""
    return ULID().hex

"""Helper functions for the Crownstone integration."""
from __future__ import annotations

import os


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path


def get_port(dev_path: str) -> str | None:
    """Get the port that the by-id link points to."""
    # not a by-id link, but just given path
    by_id = "/dev/serial/by-id"
    if by_id not in dev_path:
        return dev_path

    try:
        return f"/dev/{os.path.basename(os.readlink(dev_path))}"
    except FileNotFoundError:
        return None


def map_from_to(val: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    """Map a value from a range to another."""
    return int((val - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

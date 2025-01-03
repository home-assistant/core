"""Used to represent ScRpi commands."""

from dataclasses import dataclass


@dataclass
class Command:
    """Used to represent ScRpi commands."""

    command: str

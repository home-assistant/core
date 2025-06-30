"""Type definitions for Sure PetCare."""

from typing import TypedDict


class FlapMappings(TypedDict):
    """A TypedDict representing the mapping of entry and exit for a flap."""

    entry: str
    exit: str

"""Models for the trello integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Board:
    """A Trello board."""

    id: str
    name: str
    lists: dict[str, List]


@dataclass
class List:
    """A Trello list."""

    id: str
    name: str
    card_count: int

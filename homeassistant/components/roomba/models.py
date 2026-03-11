"""The roomba integration models."""

from dataclasses import dataclass

from roombapy import Roomba


@dataclass
class RoombaData:
    """Data for the roomba integration."""

    roomba: Roomba
    blid: str

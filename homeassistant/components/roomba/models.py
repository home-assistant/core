"""The roomba integration models."""

from dataclasses import dataclass

from roombapy import RoombaClient

from homeassistant.config_entries import ConfigEntry

type RoombaConfigEntry = ConfigEntry[RoombaData]


@dataclass
class RoombaData:
    """Data for the roomba integration."""

    roomba: RoombaClient
    blid: str

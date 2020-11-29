"""Helper for Netatmo integration."""
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class NetatmoArea:
    """Class for keeping track of an area."""

    area_name: str
    lat_ne: float
    lon_ne: float
    lat_sw: float
    lon_sw: float
    mode: str
    show_on_map: bool
    uuid: str = uuid4()

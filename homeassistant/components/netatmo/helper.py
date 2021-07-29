"""Helper for Netatmo integration."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pyatmo


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
    uuid: UUID = uuid4()


def get_all_home_ids(home_data: pyatmo.HomeData | None) -> list[str]:
    """Get all the home ids returned by NetAtmo API."""
    if home_data is None:
        return []
    return [
        home_data.homes[home_id]["id"]
        for home_id in home_data.homes
        if "modules" in home_data.homes[home_id]
    ]

"""Shade data for the Hunter Douglas PowerView integration."""

from __future__ import annotations

from dataclasses import fields
import logging
from typing import Any

from aiopvapi.resources.model import PowerviewData
from aiopvapi.resources.shade import BaseShade, ShadePosition

from .util import async_map_data_by_id

_LOGGER = logging.getLogger(__name__)

POSITION_FIELDS = [field for field in fields(ShadePosition) if field.name != "velocity"]


def copy_position_data(source: ShadePosition, target: ShadePosition) -> ShadePosition:
    """Copy position data from source to target for None values only."""
    for field in POSITION_FIELDS:
        if (value := getattr(source, field.name)) is not None:
            setattr(target, field.name, value)


class PowerviewShadeData:
    """Coordinate shade data between multiple api calls."""

    def __init__(self) -> None:
        """Init the shade data."""
        self._raw_data_by_id: dict[int, dict[str | int, Any]] = {}
        self._shade_group_data_by_id: dict[int, BaseShade] = {}
        self.positions: dict[int, ShadePosition] = {}

    def get_raw_data(self, shade_id: int) -> dict[str | int, Any]:
        """Get data for the shade."""
        return self._raw_data_by_id[shade_id]

    def get_all_raw_data(self) -> dict[int, dict[str | int, Any]]:
        """Get data for all shades."""
        return self._raw_data_by_id

    def get_shade(self, shade_id: int) -> BaseShade:
        """Get specific shade from the coordinator."""
        return self._shade_group_data_by_id[shade_id]

    def get_shade_position(self, shade_id: int) -> ShadePosition:
        """Get positions for a shade."""
        if shade_id not in self.positions:
            shade_position = ShadePosition()
            # If we have the group data, use it to populate the initial position
            if shade := self._shade_group_data_by_id.get(shade_id):
                copy_position_data(shade.current_position, shade_position)
            self.positions[shade_id] = shade_position
        return self.positions[shade_id]

    def update_from_group_data(self, shade_id: int) -> None:
        """Process an update from the group data."""
        data = self._shade_group_data_by_id[shade_id]
        copy_position_data(data.current_position, self.get_shade_position(data.id))

    def store_group_data(self, shade_data: PowerviewData) -> None:
        """Store data from the all shades endpoint.

        This does not update the shades or positions (self.positions)
        as the data may be stale. update_from_group_data
        with a shade_id will update a specific shade
        from the group data.
        """
        self._shade_group_data_by_id = shade_data.processed
        self._raw_data_by_id = async_map_data_by_id(shade_data.raw)

    def update_shade_position(self, shade_id: int, new_position: ShadePosition) -> None:
        """Update a single shades position."""
        copy_position_data(new_position, self.get_shade_position(shade_id))

    def update_shade_velocity(self, shade_id: int, shade_data: ShadePosition) -> None:
        """Update a single shades velocity."""
        # the hub will always return a velocity of 0 on initial connect,
        # separate definition to store consistent value in HA
        # this value is purely driven from HA
        if shade_data.velocity is not None:
            self.get_shade_position(shade_id).velocity = shade_data.velocity

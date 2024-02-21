"""Shade data for the Hunter Douglas PowerView integration."""
from __future__ import annotations

import logging
from typing import Any

from aiopvapi.resources.model import PowerviewData
from aiopvapi.resources.shade import BaseShade, ShadePosition

from .util import async_map_data_by_id

_LOGGER = logging.getLogger(__name__)


class PowerviewShadeData:
    """Coordinate shade data between multiple api calls."""

    def __init__(self) -> None:
        """Init the shade data."""
        self._group_data_by_id: dict[int, dict[str | int, Any]] = {}
        self._shade_data_by_id: dict[int, BaseShade] = {}
        self.positions: dict[int, ShadePosition] = {}

    def get_raw_data(self, shade_id: int) -> dict[str | int, Any]:
        """Get data for the shade."""
        return self._group_data_by_id[shade_id]

    def get_all_raw_data(self) -> dict[int, dict[str | int, Any]]:
        """Get data for all shades."""
        return self._group_data_by_id

    def get_shade(self, shade_id: int) -> BaseShade:
        """Get specific shade from the coordinator."""
        return self._shade_data_by_id[shade_id]

    def get_shade_position(self, shade_id: int) -> ShadePosition:
        """Get positions for a shade."""
        if shade_id not in self.positions:
            self.positions[shade_id] = ShadePosition()
        return self.positions[shade_id]

    def update_from_group_data(self, shade_id: int) -> None:
        """Process an update from the group data."""
        self.update_shade_positions(self._shade_data_by_id[shade_id])

    def store_group_data(self, shade_data: PowerviewData) -> None:
        """Store data from the all shades endpoint.

        This does not update the shades or positions
        as the data may be stale. update_from_group_data
        with a shade_id will update a specific shade
        from the group data.
        """
        self._shade_data_by_id = shade_data.processed
        self._group_data_by_id = async_map_data_by_id(shade_data.raw)

    def update_shade_position(self, shade_id: int, shade_data: ShadePosition) -> None:
        """Update a single shades position."""
        if shade_id not in self.positions:
            self.positions[shade_id] = ShadePosition()

        # ShadePosition will return None if the value is not set
        if shade_data.primary is not None:
            self.positions[shade_id].primary = shade_data.primary
        if shade_data.secondary is not None:
            self.positions[shade_id].secondary = shade_data.secondary
        if shade_data.tilt is not None:
            self.positions[shade_id].tilt = shade_data.tilt

    def update_shade_velocity(self, shade_id: int, shade_data: ShadePosition) -> None:
        """Update a single shades velocity."""
        if shade_id not in self.positions:
            self.positions[shade_id] = ShadePosition()

        # the hub will always return a velocity of 0 on initial connect,
        # separate definition to store consistent value in HA
        # this value is purely driven from HA
        if shade_data.velocity is not None:
            self.positions[shade_id].velocity = shade_data.velocity

    def update_shade_positions(self, data: BaseShade) -> None:
        """Update a shades from data dict."""
        _LOGGER.debug("Raw data update: %s", data.raw_data)
        self.update_shade_position(data.id, data.current_position)

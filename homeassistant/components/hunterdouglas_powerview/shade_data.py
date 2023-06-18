"""Shade data for the Hunter Douglas PowerView integration."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import logging
from typing import Any

from aiopvapi.helpers.constants import (
    ATTR_ID,
    ATTR_POSITION1,
    ATTR_POSITION2,
    ATTR_POSITION_DATA,
    ATTR_POSKIND1,
    ATTR_POSKIND2,
    ATTR_SHADE,
)
from aiopvapi.resources.shade import MIN_POSITION

from .const import POS_KIND_PRIMARY, POS_KIND_SECONDARY, POS_KIND_VANE
from .util import async_map_data_by_id

POSITIONS = ((ATTR_POSITION1, ATTR_POSKIND1), (ATTR_POSITION2, ATTR_POSKIND2))

_LOGGER = logging.getLogger(__name__)


@dataclass
class PowerviewShadeMove:
    """Request to move a powerview shade."""

    # The positions to request on the hub
    request: dict[str, int]

    # The positions that will also change
    # as a result of the request that the
    # hub will not send back
    new_positions: dict[int, int]


@dataclass
class PowerviewShadePositions:
    """Positions for a powerview shade."""

    primary: int = MIN_POSITION
    secondary: int = MIN_POSITION
    vane: int = MIN_POSITION


class PowerviewShadeData:
    """Coordinate shade data between multiple api calls."""

    def __init__(self) -> None:
        """Init the shade data."""
        self._group_data_by_id: dict[int, dict[str | int, Any]] = {}
        self.positions: dict[int, PowerviewShadePositions] = {}

    def get_raw_data(self, shade_id: int) -> dict[str | int, Any]:
        """Get data for the shade."""
        return self._group_data_by_id[shade_id]

    def get_all_raw_data(self) -> dict[int, dict[str | int, Any]]:
        """Get data for all shades."""
        return self._group_data_by_id

    def get_shade_positions(self, shade_id: int) -> PowerviewShadePositions:
        """Get positions for a shade."""
        if shade_id not in self.positions:
            self.positions[shade_id] = PowerviewShadePositions()
        return self.positions[shade_id]

    def update_from_group_data(self, shade_id: int) -> None:
        """Process an update from the group data."""
        self.update_shade_positions(self._group_data_by_id[shade_id])

    def store_group_data(self, shade_data: Iterable[dict[str | int, Any]]) -> None:
        """Store data from the all shades endpoint.

        This does not update the shades or positions
        as the data may be stale. update_from_group_data
        with a shade_id will update a specific shade
        from the group data.
        """
        self._group_data_by_id = async_map_data_by_id(shade_data)

    def update_shade_position(self, shade_id: int, position: int, kind: int) -> None:
        """Update a single shade position."""
        positions = self.get_shade_positions(shade_id)
        if kind == POS_KIND_PRIMARY:
            positions.primary = position
        elif kind == POS_KIND_SECONDARY:
            positions.secondary = position
        elif kind == POS_KIND_VANE:
            positions.vane = position

    def update_from_position_data(
        self, shade_id: int, position_data: dict[str, Any]
    ) -> None:
        """Update the shade positions from the position data."""
        for position_key, kind_key in POSITIONS:
            if position_key in position_data:
                self.update_shade_position(
                    shade_id, position_data[position_key], position_data[kind_key]
                )

    def update_shade_positions(self, data: dict[int | str, Any]) -> None:
        """Update a shades from data dict."""
        _LOGGER.debug("Raw data update: %s", data)
        shade_id = data[ATTR_ID]
        position_data = data[ATTR_POSITION_DATA]
        self.update_from_position_data(shade_id, position_data)

    def update_from_response(self, response: dict[str, Any]) -> None:
        """Update from the response to a command."""
        if response and ATTR_SHADE in response:
            shade_data: dict[int | str, Any] = response[ATTR_SHADE]
            self.update_shade_positions(shade_data)

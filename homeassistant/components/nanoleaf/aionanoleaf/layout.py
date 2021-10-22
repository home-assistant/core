# Copyright 2021, Milan Meulemans.
#
# This file is part of aionanoleaf.
#
# aionanoleaf is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# aionanoleaf is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with aionanoleaf.  If not, see <https://www.gnu.org/licenses/>.

"""Nanoleaf layout."""
from __future__ import annotations

from typing import NamedTuple

from .typing import PositionData


class Position(NamedTuple):
    """Panel position."""

    x: int
    y: int


class Shape(NamedTuple):
    """Panel shape."""

    name: str
    side_length: int | None


LIGHT_PANELS_TRIANGLE = Shape("Triangle", 150)
LIGHT_PANELS_RHYTHM = Shape("Rhythm", None)
CANVAS_SQUARE = Shape("Square", 100)
CANVAS_CONTROL_SQUARE_MASTER = Shape("Control Square Master", 100)
CANVAS_CONTROL_SQUARE_PASSIVE = Shape("Control Square Passive", 100)
SHAPES_HEXAGON = Shape("Hexagon", 67)
SHAPES_TRIANGLE = Shape("Triangle", 134)
SHAPES_MINI_TRIANGLE = Shape("Mini Triangle", 67)
SHAPES_CONTROLLER = Shape("Shapes Controller", None)
ELEMENTS_HEXAGONS = Shape("Elements Hexagons", 134)
ELEMENTS_HEXAGONS_CORNER = Shape("Elements Hexagons Corner", None)
UNKNOWN_SHAPE = Shape("Unknown", None)


class Panel:
    """Nanoleaf panel."""

    def __init__(self, panel_data: PositionData) -> None:
        """Init Nanoleaf panel."""
        self._id = panel_data["panelId"]
        self._position = Position(panel_data["x"], panel_data["y"])
        self._orientation = panel_data["o"]
        self._shape_type_id = panel_data["shapeType"]

    @property
    def id(self) -> int:
        """Return the ID."""
        return self._id

    @property
    def position(self) -> Position:
        """Return the position."""
        return self._position

    @property
    def orientation(self) -> int:
        """Return the orientation."""
        return self._orientation

    @property
    def shape(self) -> Shape:
        """Return the shape."""
        return {
            0: LIGHT_PANELS_TRIANGLE,
            1: LIGHT_PANELS_RHYTHM,
            2: CANVAS_SQUARE,
            3: CANVAS_CONTROL_SQUARE_MASTER,
            4: CANVAS_CONTROL_SQUARE_PASSIVE,
            7: SHAPES_HEXAGON,
            8: SHAPES_TRIANGLE,
            9: SHAPES_MINI_TRIANGLE,
            12: SHAPES_CONTROLLER,
            14: ELEMENTS_HEXAGONS,
            15: ELEMENTS_HEXAGONS_CORNER,
        }.get(self._shape_type_id, UNKNOWN_SHAPE)

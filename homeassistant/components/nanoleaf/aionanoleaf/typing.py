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

"""Nanoleaf API types."""
from __future__ import annotations

from typing import TypedDict


class PowerState(TypedDict):
    """Nanoleaf API power state with value."""

    value: bool


class ValueWithRange(TypedDict):
    """Nanoleaf API value, max and min."""

    value: int
    max: int
    min: int


class PositionData(TypedDict):
    """Nanoleaf API position data."""

    panelId: int
    x: int
    y: int
    o: int
    shapeType: int


class LayoutData(TypedDict):
    """Nanoleaf API layout data."""

    numPanels: int
    sideLength: int
    positionData: list[PositionData]


class PanelLayoutData(TypedDict):
    """Nanoleaf panel layout."""

    layout: LayoutData
    globalOrientation: ValueWithRange


class StateData(TypedDict):
    """Nanoleaf API state."""

    brightness: ValueWithRange
    colorMode: str
    ct: ValueWithRange
    hue: ValueWithRange
    on: PowerState
    sat: ValueWithRange


class EffectsData(TypedDict):
    """Nanoleaf API effects data."""

    select: str
    effectsList: list[str]


class InfoData(TypedDict):
    """Nanoleaf API info."""

    name: str
    serialNo: str
    manufacturer: str
    firmwareVersion: str
    model: str
    state: StateData
    effects: EffectsData
    panelLayout: PanelLayoutData


class CanvasInfoData(InfoData):
    """Nanoleaf API Canvas Panels info."""

    discovery: dict


class LightPanelsInfoData(InfoData):
    """Nanoleaf API Light Panels info."""

    rhythm: dict


class StateEventData(TypedDict):
    """Nanoleaf State event data."""

    attr: int
    value: str | int


class LayoutEventData(TypedDict):
    """Nanoleaf Layout event data."""

    attr: int


class EffectsEventData(TypedDict):
    """Nanoleaf Effects event data."""

    attr: int
    value: str


class TouchEventData(TypedDict):
    """Nanoleaf Touch event data."""

    gesture: int
    panelId: int

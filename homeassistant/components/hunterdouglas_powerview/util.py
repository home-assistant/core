"""Coordinate data for powerview devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiopvapi.helpers.constants import ATTR_ID

from homeassistant.core import callback

if TYPE_CHECKING:
    from collections.abc import Iterable


@callback
def async_map_data_by_id(data: Iterable[dict[str | int, Any]]):
    """Return a dict with the key being the id for a list of entries."""
    return {entry[ATTR_ID]: entry for entry in data}

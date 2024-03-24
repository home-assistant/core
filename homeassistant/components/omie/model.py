"""Model for the OMIE - Spain and Portugal electricity prices integration."""
from __future__ import annotations

import logging
from typing import Generic, NamedTuple, TypeVar

from pyomie.model import OMIEResults

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")


class OMIESources(NamedTuple, Generic[_T]):
    """Tuple of coordinators that source OMIE market results for today, tomorrow, and yesterday."""

    today: DataUpdateCoordinator[OMIEResults[_T] | None]
    """Today's market results (CET)."""

    tomorrow: DataUpdateCoordinator[OMIEResults[_T] | None]
    """Tomorrow's market results (CET)."""

    yesterday: DataUpdateCoordinator[OMIEResults[_T] | None]
    """Yesterday's market results (CET)."""

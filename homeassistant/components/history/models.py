"""Models for the history integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.recorder.filters import Filters
from homeassistant.helpers.entityfilter import EntityFilter


@dataclass
class HistoryConfig:
    """Configuration for the history integration."""

    sqlalchemy_filter: Filters | None = None
    entity_filter: EntityFilter | None = None

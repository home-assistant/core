"""Models states in for Recorder."""

from __future__ import annotations

from datetime import datetime
from functools import cached_property
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.engine.row import Row

from homeassistant.const import (
    COMPRESSED_STATE_ATTRIBUTES,
    COMPRESSED_STATE_LAST_CHANGED,
    COMPRESSED_STATE_LAST_UPDATED,
    COMPRESSED_STATE_STATE,
)
from homeassistant.core import Context, State
import homeassistant.util.dt as dt_util

from .state_attributes import decode_attributes_from_source

_LOGGER = logging.getLogger(__name__)

EMPTY_CONTEXT = Context(id=None)


def extract_metadata_ids(
    entity_id_to_metadata_id: dict[str, int | None],
) -> list[int]:
    """Extract metadata ids from entity_id_to_metadata_id."""
    return [
        metadata_id
        for metadata_id in entity_id_to_metadata_id.values()
        if metadata_id is not None
    ]


class LazyState(State):
    """A lazy version of core State after schema 31."""

    def __init__(  # pylint: disable=super-init-not-called
        self,
        row: Row,
        attr_cache: dict[str, dict[str, Any]],
        start_time_ts: float | None,
        entity_id: str,
        state: str,
        last_updated_ts: float | None,
        no_attributes: bool,
    ) -> None:
        """Init the lazy state."""
        self._row = row
        self.entity_id = entity_id
        self.state = state or ""
        self._attributes: dict[str, Any] | None = None
        self._last_updated_ts: float | None = last_updated_ts or start_time_ts
        self.attr_cache = attr_cache
        self.context = EMPTY_CONTEXT

    @cached_property  # type: ignore[override]
    def attributes(self) -> dict[str, Any]:
        """State attributes."""
        return decode_attributes_from_source(
            getattr(self._row, "attributes", None), self.attr_cache
        )

    @cached_property
    def _last_changed_ts(self) -> float | None:
        """Last changed timestamp."""
        return getattr(self._row, "last_changed_ts", None)

    @cached_property
    def last_changed(self) -> datetime:  # type: ignore[override]
        """Last changed datetime."""
        return dt_util.utc_from_timestamp(
            self._last_changed_ts or self._last_updated_ts  # type: ignore[arg-type]
        )

    @cached_property
    def _last_reported_ts(self) -> float | None:
        """Last reported timestamp."""
        return getattr(self._row, "last_reported_ts", None)

    @cached_property
    def last_reported(self) -> datetime:  # type: ignore[override]
        """Last reported datetime."""
        return dt_util.utc_from_timestamp(
            self._last_reported_ts or self._last_updated_ts  # type: ignore[arg-type]
        )

    @cached_property
    def last_updated(self) -> datetime:  # type: ignore[override]
        """Last updated datetime."""
        if TYPE_CHECKING:
            assert self._last_updated_ts is not None
        return dt_util.utc_from_timestamp(self._last_updated_ts)

    def as_dict(self) -> dict[str, Any]:  # type: ignore[override]
        """Return a dict representation of the LazyState.

        Async friendly.

        To be used for JSON serialization.
        """
        last_updated_isoformat = self.last_updated.isoformat()
        if self._last_changed_ts == self._last_updated_ts:
            last_changed_isoformat = last_updated_isoformat
        else:
            last_changed_isoformat = self.last_changed.isoformat()
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self._attributes or self.attributes,
            "last_changed": last_changed_isoformat,
            "last_updated": last_updated_isoformat,
        }


def row_to_compressed_state(
    row: Row,
    attr_cache: dict[str, dict[str, Any]],
    start_time_ts: float | None,
    entity_id: str,
    state: str,
    last_updated_ts: float | None,
    no_attributes: bool,
) -> dict[str, Any]:
    """Convert a database row to a compressed state schema 41 and later."""
    comp_state: dict[str, Any] = {COMPRESSED_STATE_STATE: state}
    if not no_attributes:
        comp_state[COMPRESSED_STATE_ATTRIBUTES] = decode_attributes_from_source(
            getattr(row, "attributes", None), attr_cache
        )
    row_last_updated_ts: float = last_updated_ts or start_time_ts  # type: ignore[assignment]
    comp_state[COMPRESSED_STATE_LAST_UPDATED] = row_last_updated_ts
    if (
        (row_last_changed_ts := getattr(row, "last_changed_ts", None))
        and row_last_changed_ts
        and row_last_updated_ts != row_last_changed_ts
    ):
        comp_state[COMPRESSED_STATE_LAST_CHANGED] = row_last_changed_ts
    return comp_state

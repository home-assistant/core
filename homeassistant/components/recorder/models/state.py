"""Models states in for Recorder."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

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
from .time import process_timestamp

_LOGGER = logging.getLogger(__name__)


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

    __slots__ = [
        "_row",
        "_attributes",
        "_last_changed_ts",
        "_last_updated_ts",
        "_context",
        "attr_cache",
    ]

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
        self._last_changed_ts: float | None = None
        self._context: Context | None = None
        self.attr_cache = attr_cache

    @property  # type: ignore[override]
    def attributes(self) -> dict[str, Any]:
        """State attributes."""
        if self._attributes is None:
            self._attributes = decode_attributes_from_source(
                getattr(self._row, "attributes", None), self.attr_cache
            )
        return self._attributes

    @attributes.setter
    def attributes(self, value: dict[str, Any]) -> None:
        """Set attributes."""
        self._attributes = value

    @property
    def context(self) -> Context:
        """State context."""
        if self._context is None:
            self._context = Context(id=None)
        return self._context

    @context.setter
    def context(self, value: Context) -> None:
        """Set context."""
        self._context = value

    @property
    def last_changed(self) -> datetime:
        """Last changed datetime."""
        if self._last_changed_ts is None:
            self._last_changed_ts = (
                getattr(self._row, "last_changed_ts", None) or self._last_updated_ts
            )
        return dt_util.utc_from_timestamp(self._last_changed_ts)

    @last_changed.setter
    def last_changed(self, value: datetime) -> None:
        """Set last changed datetime."""
        self._last_changed_ts = process_timestamp(value).timestamp()

    @property
    def last_updated(self) -> datetime:
        """Last updated datetime."""
        assert self._last_updated_ts is not None
        return dt_util.utc_from_timestamp(self._last_updated_ts)

    @last_updated.setter
    def last_updated(self, value: datetime) -> None:
        """Set last updated datetime."""
        self._last_updated_ts = process_timestamp(value).timestamp()

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

"""Models for Recorder."""

from __future__ import annotations

from datetime import datetime
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


class LegacyLazyState(State):
    """A lazy version of core State after schema 31."""

    __slots__ = [
        "_row",
        "_attributes",
        "_last_changed_ts",
        "_last_updated_ts",
        "_last_reported_ts",
        "_context",
        "attr_cache",
    ]

    def __init__(  # pylint: disable=super-init-not-called
        self,
        row: Row,
        attr_cache: dict[str, dict[str, Any]],
        start_time: datetime | None,
        entity_id: str | None = None,
    ) -> None:
        """Init the lazy state."""
        self._row = row
        self.entity_id = entity_id or self._row.entity_id
        self.state = self._row.state or ""
        self._attributes: dict[str, Any] | None = None
        self._last_updated_ts: float | None = self._row.last_updated_ts or (
            dt_util.utc_to_timestamp(start_time) if start_time else None
        )
        self._last_changed_ts: float | None = (
            self._row.last_changed_ts or self._last_updated_ts
        )
        self._last_reported_ts: float | None = self._last_updated_ts
        self._context: Context | None = None
        self.attr_cache = attr_cache

    @property  # type: ignore[override]
    def attributes(self) -> dict[str, Any]:
        """State attributes."""
        if self._attributes is None:
            self._attributes = decode_attributes_from_row_legacy(
                self._row, self.attr_cache
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
        assert self._last_changed_ts is not None
        return dt_util.utc_from_timestamp(self._last_changed_ts)

    @last_changed.setter
    def last_changed(self, value: datetime) -> None:
        """Set last changed datetime."""
        self._last_changed_ts = process_timestamp(value).timestamp()

    @property
    def last_reported(self) -> datetime:
        """Last reported datetime."""
        assert self._last_reported_ts is not None
        return dt_util.utc_from_timestamp(self._last_reported_ts)

    @last_reported.setter
    def last_reported(self, value: datetime) -> None:
        """Set last reported datetime."""
        self._last_reported_ts = process_timestamp(value).timestamp()

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


def legacy_row_to_compressed_state(
    row: Row,
    attr_cache: dict[str, dict[str, Any]],
    start_time: datetime | None,
    entity_id: str | None = None,
) -> dict[str, Any]:
    """Convert a database row to a compressed state schema 31 and later."""
    comp_state = {
        COMPRESSED_STATE_STATE: row.state,
        COMPRESSED_STATE_ATTRIBUTES: decode_attributes_from_row_legacy(row, attr_cache),
    }
    if start_time:
        comp_state[COMPRESSED_STATE_LAST_UPDATED] = dt_util.utc_to_timestamp(start_time)
    else:
        row_last_updated_ts: float = row.last_updated_ts
        comp_state[COMPRESSED_STATE_LAST_UPDATED] = row_last_updated_ts
        if (
            row_last_changed_ts := row.last_changed_ts
        ) and row_last_updated_ts != row_last_changed_ts:
            comp_state[COMPRESSED_STATE_LAST_CHANGED] = row_last_changed_ts
    return comp_state


def decode_attributes_from_row_legacy(
    row: Row, attr_cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Decode attributes from a database row."""
    return decode_attributes_from_source(
        getattr(row, "shared_attrs", None) or getattr(row, "attributes", None),
        attr_cache,
    )

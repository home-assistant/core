"""Helper function for Paperless-ngx sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from .coordinator import PaperlessData


@dataclass(frozen=True, kw_only=True)
class PaperlessStatusEntry:
    """Describes Paperless-ngx sensor entity."""

    state: Any
    last_run: datetime | None = None
    error: str | None = None


TState = TypeVar("TState")
TTransformed = TypeVar("TTransformed")


def get_paperless_status_entry(
    get_state: Callable[[PaperlessData], TState | None],
    get_error: Callable[[PaperlessData], str | None] | None = None,
    get_last_run: Callable[[PaperlessData], datetime | None] | None = None,
    transform: Callable[[TState], TTransformed] | None = None,
) -> Callable[[PaperlessData], PaperlessStatusEntry]:
    """Create a function to extract and transform state and error from the status object."""

    def extractor(status: PaperlessData) -> PaperlessStatusEntry:
        state = get_state(status) if get_state is not None else None
        last_run = get_last_run(status) if get_last_run is not None else None
        error = get_error(status) if get_error is not None else None

        transformed_state: TState | TTransformed | None

        if state is not None and transform is not None:
            transformed_state = transform(state)
        else:
            transformed_state = state

        return PaperlessStatusEntry(
            state=transformed_state,
            error=error,
            last_run=last_run,
        )

    return extractor


def bytes_to_gb_converter(value: int) -> float:
    """Convert bytes to gigabytes."""
    return round(value / (1024**3), 2)

"""Debug traces for conversation."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
import enum
from typing import Any

from homeassistant.util import dt as dt_util, ulid as ulid_util
from homeassistant.util.limited_size_dict import LimitedSizeDict

STORED_TRACES = 3


class ConversationTraceEventType(enum.StrEnum):
    """Type of an event emitted during a conversation."""

    ASYNC_PROCESS = "async_process"
    """The conversation is started from user input."""

    AGENT_DETAIL = "agent_detail"
    """Event detail added by a conversation agent."""

    TOOL_CALL = "tool_call"
    """A conversation agent Tool call or default agent intent call."""


@dataclass(frozen=True)
class ConversationTraceEvent:
    """Event emitted during a conversation."""

    event_type: ConversationTraceEventType
    data: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: dt_util.utcnow().isoformat())


class ConversationTrace:
    """Stores debug data related to a conversation."""

    def __init__(self) -> None:
        """Initialize ConversationTrace."""
        self._trace_id = ulid_util.ulid_now()
        self._events: list[ConversationTraceEvent] = []
        self._error: Exception | None = None
        self._result: dict[str, Any] = {}

    @property
    def trace_id(self) -> str:
        """Identifier for this trace."""
        return self._trace_id

    def add_event(self, event: ConversationTraceEvent) -> None:
        """Add an event to the trace."""
        self._events.append(event)

    def set_error(self, ex: Exception) -> None:
        """Set error."""
        self._error = ex

    def set_result(self, **kwargs: Any) -> None:
        """Set result."""
        self._result = {**kwargs}

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this ConversationTrace."""
        result: dict[str, Any] = {
            "id": self._trace_id,
            "events": [asdict(event) for event in self._events],
        }
        if self._error is not None:
            result["error"] = str(self._error) or self._error.__class__.__name__
        if self._result is not None:
            result["result"] = self._result
        return result


_current_trace: ContextVar[ConversationTrace | None] = ContextVar(
    "current_trace", default=None
)
_recent_traces: LimitedSizeDict[str, ConversationTrace] = LimitedSizeDict(
    size_limit=STORED_TRACES
)


def async_conversation_trace_append(
    event_type: ConversationTraceEventType, event_data: dict[str, Any]
) -> None:
    """Append a ConversationTraceEvent to the current active trace."""
    trace = _current_trace.get()
    if not trace:
        return
    trace.add_event(ConversationTraceEvent(event_type, event_data))


@contextmanager
def async_conversation_trace() -> Generator[ConversationTrace]:
    """Create a new active ConversationTrace."""
    trace = ConversationTrace()
    token = _current_trace.set(trace)
    _recent_traces[trace.trace_id] = trace
    try:
        yield trace
    except Exception as ex:
        trace.set_error(ex)
        raise
    finally:
        _current_trace.reset(token)


def async_get_traces() -> list[ConversationTrace]:
    """Get the most recent traces."""
    return list(_recent_traces.values())


def async_clear_traces() -> None:
    """Clear all traces."""
    _recent_traces.clear()

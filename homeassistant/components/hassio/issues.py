"""Supervisor issue models."""

from dataclasses import dataclass, field
from typing import NotRequired, TypedDict
from uuid import UUID

from aiohasupervisor.models import ContextType


class SuggestionDataType(TypedDict):
    """Suggestion dictionary as received from supervisor."""

    uuid: str
    type: str
    context: str
    reference: str | None


@dataclass(slots=True, frozen=True)
class Suggestion:
    """Suggestion from Supervisor which resolves an issue."""

    uuid: UUID
    type: str
    context: ContextType
    reference: str | None = None

    @property
    def key(self) -> str:
        """Get key for suggestion (combination of context and type)."""
        return f"{self.context}_{self.type}"

    @classmethod
    def from_dict(cls, data: SuggestionDataType) -> Suggestion:
        """Convert from dictionary representation."""
        return cls(
            uuid=UUID(data["uuid"]),
            type=data["type"],
            context=ContextType(data["context"]),
            reference=data["reference"],
        )


class IssueDataType(TypedDict):
    """Issue dictionary as received from supervisor."""

    uuid: str
    type: str
    context: str
    reference: str | None
    suggestions: NotRequired[list[SuggestionDataType]]


@dataclass(slots=True, frozen=True)
class Issue:
    """Issue from Supervisor."""

    uuid: UUID
    type: str
    context: ContextType
    reference: str | None = None
    suggestions: list[Suggestion] = field(default_factory=list, compare=False)

    @property
    def key(self) -> str:
        """Get key for issue (combination of context and type)."""
        return f"issue_{self.context}_{self.type}"

    @classmethod
    def from_dict(cls, data: IssueDataType) -> Issue:
        """Convert from dictionary representation."""
        suggestions: list[SuggestionDataType] = data.get("suggestions", [])
        return cls(
            uuid=UUID(data["uuid"]),
            type=data["type"],
            context=ContextType(data["context"]),
            reference=data["reference"],
            suggestions=[
                Suggestion.from_dict(suggestion) for suggestion in suggestions
            ],
        )

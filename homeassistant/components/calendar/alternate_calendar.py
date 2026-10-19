"""Alternate calendar support for the calendar integration."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
from typing import Any, ClassVar


@dataclass(frozen=True)
class AlternateDate:
    """A date in an alternate calendar system."""

    calendar_type: str
    display_name: str
    date_str: str
    metadata: dict[str, Any] | None = None


class AlternateCalendarProvider(ABC):
    """Base class for alternate calendar providers."""

    @property
    @abstractmethod
    def calendar_type(self) -> str:
        """Return the identifier of the alternate calendar system."""

    @property
    def display_name(self) -> str:
        """Return the human-readable name of the alternate calendar system."""
        return self.calendar_type.replace("_", " ").title()

    @abstractmethod
    def convert_date(self, gregorian_date: dt.date) -> AlternateDate:
        """Convert a Gregorian date to an alternate calendar date."""


class AlternateCalendarRegistry:
    """Registry for alternate calendar providers."""

    _providers: ClassVar[dict[str, type[AlternateCalendarProvider]]] = {}

    @classmethod
    def register(
        cls, calendar_type: str
    ) -> Callable[[type[AlternateCalendarProvider]], type[AlternateCalendarProvider]]:
        """Return a decorator that registers a provider for a calendar type."""

        def decorator(
            provider: type[AlternateCalendarProvider],
        ) -> type[AlternateCalendarProvider]:
            cls._providers[calendar_type] = provider
            return provider

        return decorator

    @classmethod
    def get_provider(cls, calendar_type: str) -> type[AlternateCalendarProvider]:
        """Return the provider class registered for a calendar type."""
        try:
            return cls._providers[calendar_type]
        except KeyError:
            raise KeyError(
                f"No provider registered for alternate calendar type: {calendar_type}"
            ) from None

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return all registered alternate calendar type identifiers."""
        return list(cls._providers)

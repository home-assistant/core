"""Template render information tracking for Home Assistant."""

from __future__ import annotations

import collections.abc
from collections.abc import Callable
from contextvars import ContextVar
from typing import TYPE_CHECKING, cast

from homeassistant.core import split_entity_id

if TYPE_CHECKING:
    from homeassistant.exceptions import TemplateError

    from . import Template

# Rate limiting constants
ALL_STATES_RATE_LIMIT = 60  # seconds
DOMAIN_STATES_RATE_LIMIT = 1  # seconds

# Context variable for render information tracking
render_info_cv: ContextVar[RenderInfo | None] = ContextVar(
    "render_info_cv", default=None
)


# Filter functions for efficiency
def _true(entity_id: str) -> bool:
    """Return True for all entity IDs."""
    return True


def _false(entity_id: str) -> bool:
    """Return False for all entity IDs."""
    return False


class RenderInfo:
    """Holds information about a template render."""

    __slots__ = (
        "_result",
        "all_states",
        "all_states_lifecycle",
        "domains",
        "domains_lifecycle",
        "entities",
        "exception",
        "filter",
        "filter_lifecycle",
        "has_time",
        "is_static",
        "rate_limit",
        "template",
    )

    def __init__(self, template: Template) -> None:
        """Initialise."""
        self.template = template
        # Will be set sensibly once frozen.
        self.filter_lifecycle: Callable[[str], bool] = _true
        self.filter: Callable[[str], bool] = _true
        self._result: str | None = None
        self.is_static = False
        self.exception: TemplateError | None = None
        self.all_states = False
        self.all_states_lifecycle = False
        self.domains: collections.abc.Set[str] = set()
        self.domains_lifecycle: collections.abc.Set[str] = set()
        self.entities: collections.abc.Set[str] = set()
        self.rate_limit: float | None = None
        self.has_time = False

    def __repr__(self) -> str:
        """Representation of RenderInfo."""
        return (
            f"<RenderInfo {self.template}"
            f" all_states={self.all_states}"
            f" all_states_lifecycle={self.all_states_lifecycle}"
            f" domains={self.domains}"
            f" domains_lifecycle={self.domains_lifecycle}"
            f" entities={self.entities}"
            f" rate_limit={self.rate_limit}"
            f" has_time={self.has_time}"
            f" exception={self.exception}"
            f" is_static={self.is_static}"
            ">"
        )

    def _filter_domains_and_entities(self, entity_id: str) -> bool:
        """Template should re-render if the entity state changes.

        Only when we match specific domains or entities.
        """
        return (
            split_entity_id(entity_id)[0] in self.domains or entity_id in self.entities
        )

    def _filter_entities(self, entity_id: str) -> bool:
        """Template should re-render if the entity state changes.

        Only when we match specific entities.
        """
        return entity_id in self.entities

    def _filter_lifecycle_domains(self, entity_id: str) -> bool:
        """Template should re-render if the entity is added or removed.

        Only with domains watched.
        """
        return split_entity_id(entity_id)[0] in self.domains_lifecycle

    def result(self) -> str:
        """Results of the template computation."""
        if self.exception is not None:
            raise self.exception
        return cast(str, self._result)

    def _freeze_static(self) -> None:
        self.is_static = True
        self._freeze_sets()
        self.all_states = False

    def _freeze_sets(self) -> None:
        self.entities = frozenset(self.entities)
        self.domains = frozenset(self.domains)
        self.domains_lifecycle = frozenset(self.domains_lifecycle)

    def _freeze(self) -> None:
        self._freeze_sets()

        if self.rate_limit is None:
            if self.all_states or self.exception:
                self.rate_limit = ALL_STATES_RATE_LIMIT
            elif self.domains or self.domains_lifecycle:
                self.rate_limit = DOMAIN_STATES_RATE_LIMIT

        if self.exception:
            return

        if not self.all_states_lifecycle:
            if self.domains_lifecycle:
                self.filter_lifecycle = self._filter_lifecycle_domains
            else:
                self.filter_lifecycle = _false

        if self.all_states:
            return

        if self.domains:
            self.filter = self._filter_domains_and_entities
        elif self.entities:
            self.filter = self._filter_entities
        else:
            self.filter = _false

"""Helper class to implement include/exclude of entities and domains."""
from typing import Callable, Dict, Iterable, Any, Optional, Set

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.helpers import config_validation as cv

CONF_INCLUDE_DOMAINS = 'include_domains'
CONF_INCLUDE_ENTITIES = 'include_entities'
CONF_EXCLUDE_DOMAINS = 'exclude_domains'
CONF_EXCLUDE_ENTITIES = 'exclude_entities'


def _convert_filter(config: Dict[str, Iterable[str]]) -> Callable[[str], bool]:
    filt = generate_filter(
        config[CONF_INCLUDE_DOMAINS],
        config[CONF_INCLUDE_ENTITIES],
        config[CONF_EXCLUDE_DOMAINS],
        config[CONF_EXCLUDE_ENTITIES],
    )
    setattr(filt, 'config', config)
    return filt


FILTER_SCHEMA = vol.All(
    vol.Schema({
        vol.Optional(CONF_EXCLUDE_DOMAINS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXCLUDE_ENTITIES, default=[]): cv.entity_ids,
        vol.Optional(CONF_INCLUDE_DOMAINS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_INCLUDE_ENTITIES, default=[]): cv.entity_ids,
    }), _convert_filter)


def generate_filter(include_domains: Iterable[str],
                    include_entities: Iterable[str],
                    exclude_domains: Iterable[str],
                    exclude_entities: Iterable[str]) -> Callable[[str], bool]:
    """Return a function that will filter entities based on the args."""
    # Case 1 - no includes or excludes - pass all entities
    if (not include_domains and not include_entities
            and not exclude_domains and not exclude_entities):
        return EntityFilter(include_all=True)

    return EntityFilter(include_domains=include_domains,
                        include_entities=include_entities,
                        exclude_domains=exclude_domains,
                        exclude_entities=exclude_entities)


class EntityFilter:
    """Filter for entitity IDs."""

    def __init__(self, include_all: bool = False,
                 include_domains: Optional[Iterable[str]] = None,
                 include_entities: Optional[Iterable[str]] = None,
                 exclude_domains: Optional[Iterable[str]] = None,
                 exclude_entities: Optional[Iterable[str]] = None):
        """Initialiser."""
        self.include_all = include_all
        self._include_domains = set(include_domains or [])
        self._include_entities = set(include_entities or [])
        self._exclude_domains = set(exclude_domains or [])
        self._exclude_entities = set(exclude_entities or [])

    @property
    def include_domains(self) -> Set[str]:
        """Domains included in the filter."""
        return self._include_domains

    @property
    def include_entities(self) -> Set[str]:
        """Entities included in the filter."""
        return self._include_entities

    @property
    def exclude_domains(self) -> Set[str]:
        """Domains excluded from the filter."""
        return self._exclude_domains

    @property
    def exclude_entities(self) -> Set[str]:
        """Entities excluded from the filter."""
        return self._exclude_entities

    def __eq__(self, other: Any) -> bool:
        """Test equivalence of two filters."""
        if isinstance(other, EntityFilter):
            return (
                self.include_all == other.include_all and
                self._include_domains == other.include_domains and
                self._include_entities == other.include_entities and
                self._exclude_domains == other.exclude_domains and
                self._exclude_entities == other.exclude_entities)
        return False

    def __repr__(self) -> str:
        """Convert to string."""
        return (
            "EntityFilter(" +
            ("include_all=True " if self.include_all else "") +
            (("include_domains=" + str(self._include_domains) + " ")
             if self._include_domains else "") +
            (("include_entities=" + str(self._include_entities) + " ")
             if self._include_entities else "") +
            (("exclude_domains=" + str(self._exclude_domains) + " ")
             if self._exclude_domains else "") +
            (("exclude_entities=" + str(self._exclude_entities) + " ")
             if self._exclude_entities else "") +
            ")")

    def __call__(self, entity_id: str) -> bool:
        """Filter entities based on the filter."""
        # Case 1 - pass all entities
        if self.include_all:
            return True

        have_exclude = bool(self._exclude_entities or self._exclude_domains)
        have_include = bool(self._include_entities or self._include_domains)

        # Case 1a - fail all entities
        if not have_exclude and not have_include:
            return False

        # Case 2 - includes, no excludes - only include specified entities
        if have_include and not have_exclude:
            return (entity_id in self._include_entities or
                    split_entity_id(entity_id)[0] in self._include_domains)

        # Case 3 - excludes, no includes - only exclude specified entities
        if not have_include and have_exclude:
            return (entity_id not in self._exclude_entities and
                    split_entity_id(entity_id)[0] not in self._exclude_domains)

        # Case 4 - both includes and excludes specified
        # Case 4a - include domain specified
        #  - if domain is included, pass if entity not excluded
        #  - if domain is not included, pass if entity is included
        # note: if both include and exclude domains specified,
        #   the exclude domains are ignored
        if self._include_domains:
            domain = split_entity_id(entity_id)[0]
            if domain in self._include_domains:
                return entity_id not in self._exclude_entities
            return entity_id in self._include_entities

        # Case 4b - exclude domain specified
        #  - if domain is excluded, pass if entity is included
        #  - if domain is not excluded, pass if entity not excluded
        if self._exclude_domains:
            domain = split_entity_id(entity_id)[0]
            if domain in self._exclude_domains:
                return entity_id in self._include_entities
            return entity_id not in self._exclude_entities

        # Case 4c - neither include or exclude domain specified
        #  - Only pass if entity is included.  Ignore entity excludes.
        return entity_id in self._include_entities

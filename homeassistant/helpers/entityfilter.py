"""Helper class to implement include/exclude of entities and domains."""
from typing import Callable, Dict, Iterable, Any, Optional

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
    include_d = set(include_domains)
    include_e = set(include_entities)
    exclude_d = set(exclude_domains)
    exclude_e = set(exclude_entities)

    have_exclude = bool(exclude_e or exclude_d)
    have_include = bool(include_e or include_d)

    # Case 1 - no includes or excludes - pass all entities
    if not have_include and not have_exclude:
        return lambda entity_id: True

    # Case 2 - includes, no excludes - only include specified entities
    if have_include and not have_exclude:
        def entity_filter_2(entity_id: str) -> bool:
            """Return filter function for case 2."""
            domain = split_entity_id(entity_id)[0]
            return (entity_id in include_e or
                    domain in include_d)

        return entity_filter_2

    # Case 3 - excludes, no includes - only exclude specified entities
    if not have_include and have_exclude:
        def entity_filter_3(entity_id: str) -> bool:
            """Return filter function for case 3."""
            domain = split_entity_id(entity_id)[0]
            return (entity_id not in exclude_e and
                    domain not in exclude_d)

        return entity_filter_3

    # Case 4 - both includes and excludes specified
    # Case 4a - include domain specified
    #  - if domain is included, pass if entity not excluded
    #  - if domain is not included, pass if entity is included
    # note: if both include and exclude domains specified,
    #   the exclude domains are ignored
    if include_d:
        def entity_filter_4a(entity_id: str) -> bool:
            """Return filter function for case 4a."""
            domain = split_entity_id(entity_id)[0]
            if domain in include_d:
                return entity_id not in exclude_e
            return entity_id in include_e

        return entity_filter_4a

    # Case 4b - exclude domain specified
    #  - if domain is excluded, pass if entity is included
    #  - if domain is not excluded, pass if entity not excluded
    if exclude_d:
        def entity_filter_4b(entity_id: str) -> bool:
            """Return filter function for case 4b."""
            domain = split_entity_id(entity_id)[0]
            if domain in exclude_d:
                return entity_id in include_e
            return entity_id not in exclude_e

        return entity_filter_4b

    # Case 4c - neither include or exclude domain specified
    #  - Only pass if entity is included.  Ignore entity excludes.
    def entity_filter_4c(entity_id: str) -> bool:
        """Return filter function for case 4c."""
        return entity_id in include_e

    return entity_filter_4c


class FilterBuilder:
    """Builder class for entity filters."""

    def __init__(self, include_all: bool = False,
                 include_domains: Optional[Iterable[str]] = None,
                 include_entities: Optional[Iterable[str]] = None,
                 exclude_domains: Optional[Iterable[str]] = None,
                 exclude_entities: Optional[Iterable[str]] = None):
        """Initialiser."""
        self.include_all = include_all
        self.include_domains = set(include_domains or [])
        self.include_entities = set(include_entities or [])
        self.exclude_domains = set(exclude_domains or [])
        self.exclude_entities = set(exclude_entities or [])

    def build(self) -> Callable[[str], bool]:
        """Build a callable entity filter based on current settings."""
        if self.include_all:
            return lambda _: True
        if (not self.include_domains
                and not self.include_entities
                and not self.exclude_entities
                and not self.exclude_entities):
            return lambda _: False

        return generate_filter(
            self.include_domains,
            self.include_entities,
            self.exclude_domains,
            self.exclude_entities)

    def __call__(self, entity_id: str) -> bool:
        """Build filter and evaluate for given entity_id."""
        return self.build()(entity_id)

    def __eq__(self, other: Any) -> bool:
        """Test equivalence of two filter builders, or list of entities."""
        if isinstance(other, FilterBuilder):
            return (
                self.include_all == other.include_all and
                self.include_domains == other.include_domains and
                self.include_entities == other.include_entities and
                self.exclude_domains == other.exclude_domains and
                self.exclude_entities == other.exclude_entities)
        return False

    def __repr__(self) -> str:
        """Convert to string."""
        return (
            "FilterBuilder(" +
            ("include_all=True " if self.include_all else "") +
            (("include_domains=" + str(self.include_domains) + " ")
             if self.include_domains else "") +
            (("include_entities=" + str(self.include_entities) + " ")
             if self.include_entities else "") +
            (("exclude_domains=" + str(self.exclude_domains) + " ")
             if self.exclude_domains else "") +
            (("exclude_entities=" + str(self.exclude_entities) + " ")
             if self.exclude_entities else ""))

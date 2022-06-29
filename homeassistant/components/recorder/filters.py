"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections.abc import Callable, Iterable
import json
from typing import Any

from sqlalchemy import Column, Text, cast, not_, or_
from sqlalchemy.sql.elements import ClauseList

from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.helpers.entityfilter import CONF_ENTITY_GLOBS
from homeassistant.helpers.typing import ConfigType

from .db_schema import ENTITY_ID_IN_EVENT, OLD_ENTITY_ID_IN_EVENT, States

DOMAIN = "history"
HISTORY_FILTERS = "history_filters"
JSON_NULL = json.dumps(None)

GLOB_TO_SQL_CHARS = {
    ord("*"): "%",
    ord("?"): "_",
    ord("%"): "\\%",
    ord("_"): "\\_",
    ord("\\"): "\\\\",
}

FILTER_TYPES = (CONF_EXCLUDE, CONF_INCLUDE)
FITLER_MATCHERS = (CONF_ENTITIES, CONF_DOMAINS, CONF_ENTITY_GLOBS)


def extract_include_exclude_filter_conf(conf: ConfigType) -> dict[str, Any]:
    """Extract an include exclude filter from configuration.

    This makes a copy so we do not alter the original data.
    """
    return {
        filter_type: {
            matcher: set(conf.get(filter_type, {}).get(matcher) or [])
            for matcher in FITLER_MATCHERS
        }
        for filter_type in FILTER_TYPES
    }


def merge_include_exclude_filters(
    base_filter: dict[str, Any], add_filter: dict[str, Any]
) -> dict[str, Any]:
    """Merge two filters.

    This makes a copy so we do not alter the original data.
    """
    return {
        filter_type: {
            matcher: base_filter[filter_type][matcher]
            | add_filter[filter_type][matcher]
            for matcher in FITLER_MATCHERS
        }
        for filter_type in FILTER_TYPES
    }


def sqlalchemy_filter_from_include_exclude_conf(conf: ConfigType) -> Filters | None:
    """Build a sql filter from config."""
    filters = Filters()
    if exclude := conf.get(CONF_EXCLUDE):
        filters.excluded_entities = exclude.get(CONF_ENTITIES, [])
        filters.excluded_domains = exclude.get(CONF_DOMAINS, [])
        filters.excluded_entity_globs = exclude.get(CONF_ENTITY_GLOBS, [])
    if include := conf.get(CONF_INCLUDE):
        filters.included_entities = include.get(CONF_ENTITIES, [])
        filters.included_domains = include.get(CONF_DOMAINS, [])
        filters.included_entity_globs = include.get(CONF_ENTITY_GLOBS, [])

    return filters if filters.has_config else None


class Filters:
    """Container for the configured include and exclude filters."""

    def __init__(self) -> None:
        """Initialise the include and exclude filters."""
        self.excluded_entities: Iterable[str] = []
        self.excluded_domains: Iterable[str] = []
        self.excluded_entity_globs: Iterable[str] = []

        self.included_entities: Iterable[str] = []
        self.included_domains: Iterable[str] = []
        self.included_entity_globs: Iterable[str] = []

    def __repr__(self) -> str:
        """Return human readable excludes/includes."""
        return (
            f"<Filters excluded_entities={self.excluded_entities} excluded_domains={self.excluded_domains} "
            f"excluded_entity_globs={self.excluded_entity_globs} "
            f"included_entities={self.included_entities} included_domains={self.included_domains} "
            f"included_entity_globs={self.included_entity_globs}>"
        )

    @property
    def has_config(self) -> bool:
        """Determine if there is any filter configuration."""
        return bool(self._have_exclude or self._have_include)

    @property
    def _have_exclude(self) -> bool:
        return bool(
            self.excluded_entities
            or self.excluded_domains
            or self.excluded_entity_globs
        )

    @property
    def _have_include(self) -> bool:
        return bool(
            self.included_entities
            or self.included_domains
            or self.included_entity_globs
        )

    def _generate_filter_for_columns(
        self, columns: Iterable[Column], encoder: Callable[[Any], Any]
    ) -> ClauseList:
        """Generate a filter from pre-comuted sets and pattern lists.

        This must match exactly how homeassistant.helpers.entityfilter works.
        """
        i_domains = _domain_matcher(self.included_domains, columns, encoder)
        i_entities = _entity_matcher(self.included_entities, columns, encoder)
        i_entity_globs = _globs_to_like(self.included_entity_globs, columns, encoder)
        includes = [i_domains, i_entities, i_entity_globs]

        e_domains = _domain_matcher(self.excluded_domains, columns, encoder)
        e_entities = _entity_matcher(self.excluded_entities, columns, encoder)
        e_entity_globs = _globs_to_like(self.excluded_entity_globs, columns, encoder)
        excludes = [e_domains, e_entities, e_entity_globs]

        have_exclude = self._have_exclude
        have_include = self._have_include

        # Case 1 - No filter
        # - All entities included
        if not have_include and not have_exclude:
            return None

        # Case 2 - Only includes
        # - Entity listed in entities include: include
        # - Otherwise, entity matches domain include: include
        # - Otherwise, entity matches glob include: include
        # - Otherwise: exclude
        if have_include and not have_exclude:
            return or_(*includes).self_group()

        # Case 3 - Only excludes
        # - Entity listed in exclude: exclude
        # - Otherwise, entity matches domain exclude: exclude
        # - Otherwise, entity matches glob exclude: exclude
        # - Otherwise: include
        if not have_include and have_exclude:
            return not_(or_(*excludes).self_group())

        # Case 4 - Domain and/or glob includes (may also have excludes)
        # - Entity listed in entities include: include
        # - Otherwise, entity listed in entities exclude: exclude
        # - Otherwise, entity matches glob include: include
        # - Otherwise, entity matches glob exclude: exclude
        # - Otherwise, entity matches domain include: include
        # - Otherwise: exclude
        if self.included_domains or self.included_entity_globs:
            return or_(
                i_entities,
                (~e_entities & (i_entity_globs | (~e_entity_globs & i_domains))),
            ).self_group()

        # Case 5 - Domain and/or glob excludes (no domain and/or glob includes)
        # - Entity listed in entities include: include
        # - Otherwise, entity listed in exclude: exclude
        # - Otherwise, entity matches glob exclude: exclude
        # - Otherwise, entity matches domain exclude: exclude
        # - Otherwise: include
        if self.excluded_domains or self.excluded_entity_globs:
            return (not_(or_(*excludes)) | i_entities).self_group()

        # Case 6 - No Domain and/or glob includes or excludes
        # - Entity listed in entities include: include
        # - Otherwise: exclude
        return i_entities

    def states_entity_filter(self) -> ClauseList:
        """Generate the entity filter query."""

        def _encoder(data: Any) -> Any:
            """Nothing to encode for states since there is no json."""
            return data

        return self._generate_filter_for_columns((States.entity_id,), _encoder)

    def events_entity_filter(self) -> ClauseList:
        """Generate the entity filter query."""
        _encoder = json.dumps
        return or_(
            # sqlalchemy's SQLite json implementation always
            # wraps everything with JSON_QUOTE so it resolves to 'null'
            # when its empty
            #
            # For MySQL and PostgreSQL it will resolve to a literal
            # NULL when its empty
            #
            ((ENTITY_ID_IN_EVENT == JSON_NULL) | ENTITY_ID_IN_EVENT.is_(None))
            & (
                (OLD_ENTITY_ID_IN_EVENT == JSON_NULL) | OLD_ENTITY_ID_IN_EVENT.is_(None)
            ),
            self._generate_filter_for_columns(
                (ENTITY_ID_IN_EVENT, OLD_ENTITY_ID_IN_EVENT), _encoder
            ).self_group(),
        )


def _globs_to_like(
    glob_strs: Iterable[str], columns: Iterable[Column], encoder: Callable[[Any], Any]
) -> ClauseList:
    """Translate glob to sql."""
    matchers = [
        (
            column.is_not(None)
            & cast(column, Text()).like(
                encoder(glob_str).translate(GLOB_TO_SQL_CHARS), escape="\\"
            )
        )
        for glob_str in glob_strs
        for column in columns
    ]
    return or_(*matchers) if matchers else or_(False)


def _entity_matcher(
    entity_ids: Iterable[str], columns: Iterable[Column], encoder: Callable[[Any], Any]
) -> ClauseList:
    matchers = [
        (
            column.is_not(None)
            & cast(column, Text()).in_([encoder(entity_id) for entity_id in entity_ids])
        )
        for column in columns
    ]
    return or_(*matchers) if matchers else or_(False)


def _domain_matcher(
    domains: Iterable[str], columns: Iterable[Column], encoder: Callable[[Any], Any]
) -> ClauseList:
    matchers = [
        (column.is_not(None) & cast(column, Text()).like(encoder(domain_matcher)))
        for domain_matcher in like_domain_matchers(domains)
        for column in columns
    ]
    return or_(*matchers) if matchers else or_(False)


def like_domain_matchers(domains: Iterable[str]) -> list[str]:
    """Convert a list of domains to sql LIKE matchers."""
    return [f"{domain}.%" for domain in domains]

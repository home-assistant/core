"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections.abc import Callable, Iterable
import json
from typing import Any

from sqlalchemy import JSON, Column, Text, cast, not_, or_
from sqlalchemy.sql.elements import ClauseList

from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.helpers.entityfilter import CONF_ENTITY_GLOBS
from homeassistant.helpers.typing import ConfigType

from .models import ENTITY_ID_IN_EVENT, OLD_ENTITY_ID_IN_EVENT, States

DOMAIN = "history"
HISTORY_FILTERS = "history_filters"

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
            matcher: set(conf.get(filter_type, {}).get(matcher, []))
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

    @property
    def has_config(self) -> bool:
        """Determine if there is any filter configuration."""
        return bool(
            self.excluded_entities
            or self.excluded_domains
            or self.excluded_entity_globs
            or self.included_entities
            or self.included_domains
            or self.included_entity_globs
        )

    def _generate_filter_for_columns(
        self, columns: Iterable[Column], encoder: Callable[[Any], Any]
    ) -> ClauseList:
        includes = []
        if self.included_domains:
            includes.append(_domain_matcher(self.included_domains, columns, encoder))
        if self.included_entities:
            includes.append(_entity_matcher(self.included_entities, columns, encoder))
        if self.included_entity_globs:
            includes.append(
                _globs_to_like(self.included_entity_globs, columns, encoder)
            )

        excludes = []
        if self.excluded_domains:
            excludes.append(_domain_matcher(self.excluded_domains, columns, encoder))
        if self.excluded_entities:
            excludes.append(_entity_matcher(self.excluded_entities, columns, encoder))
        if self.excluded_entity_globs:
            excludes.append(
                _globs_to_like(self.excluded_entity_globs, columns, encoder)
            )

        if not includes and not excludes:
            return None

        if includes and not excludes:
            return or_(*includes).self_group()

        if not includes and excludes:
            return not_(or_(*excludes).self_group())

        return or_(*includes).self_group() & not_(or_(*excludes).self_group())

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
            (ENTITY_ID_IN_EVENT == JSON.NULL) & (OLD_ENTITY_ID_IN_EVENT == JSON.NULL),
            self._generate_filter_for_columns(
                (ENTITY_ID_IN_EVENT, OLD_ENTITY_ID_IN_EVENT), _encoder
            ).self_group(),
        )


def _globs_to_like(
    glob_strs: Iterable[str], columns: Iterable[Column], encoder: Callable[[Any], Any]
) -> ClauseList:
    """Translate glob to sql."""
    return or_(
        cast(column, Text()).like(
            encoder(glob_str).translate(GLOB_TO_SQL_CHARS), escape="\\"
        )
        for glob_str in glob_strs
        for column in columns
    )


def _entity_matcher(
    entity_ids: Iterable[str], columns: Iterable[Column], encoder: Callable[[Any], Any]
) -> ClauseList:
    return or_(
        cast(column, Text()).in_([encoder(entity_id) for entity_id in entity_ids])
        for column in columns
    )


def _domain_matcher(
    domains: Iterable[str], columns: Iterable[Column], encoder: Callable[[Any], Any]
) -> ClauseList:
    return or_(
        cast(column, Text()).like(encoder(f"{domain}.%"))
        for domain in domains
        for column in columns
    )

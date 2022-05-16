"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from sqlalchemy import not_, or_
from sqlalchemy.sql.elements import ClauseList

from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.helpers.entityfilter import CONF_ENTITY_GLOBS
from homeassistant.helpers.typing import ConfigType

from .models import States

DOMAIN = "history"
HISTORY_FILTERS = "history_filters"

GLOB_TO_SQL_CHARS = {
    42: "%",  # *
    46: "_",  # .
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
        self.excluded_entities: list[str] = []
        self.excluded_domains: list[str] = []
        self.excluded_entity_globs: list[str] = []

        self.included_entities: list[str] = []
        self.included_domains: list[str] = []
        self.included_entity_globs: list[str] = []

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

    def entity_filter(self) -> ClauseList:
        """Generate the entity filter query."""
        includes = []
        if self.included_domains:
            includes.append(
                or_(
                    *[
                        States.entity_id.like(f"{domain}.%")
                        for domain in self.included_domains
                    ]
                ).self_group()
            )
        if self.included_entities:
            includes.append(States.entity_id.in_(self.included_entities))
        for glob in self.included_entity_globs:
            includes.append(_glob_to_like(glob))

        excludes = []
        if self.excluded_domains:
            excludes.append(
                or_(
                    *[
                        States.entity_id.like(f"{domain}.%")
                        for domain in self.excluded_domains
                    ]
                ).self_group()
            )
        if self.excluded_entities:
            excludes.append(States.entity_id.in_(self.excluded_entities))
        for glob in self.excluded_entity_globs:
            excludes.append(_glob_to_like(glob))

        if not includes and not excludes:
            return None

        if includes and not excludes:
            return or_(*includes)

        if not includes and excludes:
            return not_(or_(*excludes))

        return or_(*includes) & not_(or_(*excludes))


def _glob_to_like(glob_str: str) -> ClauseList:
    """Translate glob to sql."""
    return States.entity_id.like(glob_str.translate(GLOB_TO_SQL_CHARS))

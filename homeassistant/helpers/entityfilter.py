"""Helper class to implement include/exclude of entities and domains."""
from __future__ import annotations

from collections.abc import Callable
import fnmatch
import re

import voluptuous as vol

from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import split_entity_id
from homeassistant.helpers import config_validation as cv

CONF_INCLUDE_DOMAINS = "include_domains"
CONF_INCLUDE_ENTITY_GLOBS = "include_entity_globs"
CONF_INCLUDE_ENTITIES = "include_entities"
CONF_EXCLUDE_DOMAINS = "exclude_domains"
CONF_EXCLUDE_ENTITY_GLOBS = "exclude_entity_globs"
CONF_EXCLUDE_ENTITIES = "exclude_entities"

CONF_ENTITY_GLOBS = "entity_globs"


def convert_filter(config: dict[str, list[str]]) -> Callable[[str], bool]:
    """Convert the filter schema into a filter."""
    filt = generate_filter(
        config[CONF_INCLUDE_DOMAINS],
        config[CONF_INCLUDE_ENTITIES],
        config[CONF_EXCLUDE_DOMAINS],
        config[CONF_EXCLUDE_ENTITIES],
        config[CONF_INCLUDE_ENTITY_GLOBS],
        config[CONF_EXCLUDE_ENTITY_GLOBS],
    )
    setattr(filt, "config", config)
    setattr(filt, "empty_filter", sum(len(val) for val in config.values()) == 0)
    return filt


BASE_FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EXCLUDE_DOMAINS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EXCLUDE_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EXCLUDE_ENTITIES, default=[]): cv.entity_ids,
        vol.Optional(CONF_INCLUDE_DOMAINS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_INCLUDE_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_INCLUDE_ENTITIES, default=[]): cv.entity_ids,
    }
)

FILTER_SCHEMA = vol.All(BASE_FILTER_SCHEMA, convert_filter)


def convert_include_exclude_filter(
    config: dict[str, dict[str, list[str]]]
) -> Callable[[str], bool]:
    """Convert the include exclude filter schema into a filter."""
    include = config[CONF_INCLUDE]
    exclude = config[CONF_EXCLUDE]
    filt = convert_filter(
        {
            CONF_INCLUDE_DOMAINS: include[CONF_DOMAINS],
            CONF_INCLUDE_ENTITY_GLOBS: include[CONF_ENTITY_GLOBS],
            CONF_INCLUDE_ENTITIES: include[CONF_ENTITIES],
            CONF_EXCLUDE_DOMAINS: exclude[CONF_DOMAINS],
            CONF_EXCLUDE_ENTITY_GLOBS: exclude[CONF_ENTITY_GLOBS],
            CONF_EXCLUDE_ENTITIES: exclude[CONF_ENTITIES],
        }
    )
    setattr(filt, "config", config)
    return filt


INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER = vol.Schema(
    {
        vol.Optional(CONF_DOMAINS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
    }
)

INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_INCLUDE, default=INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER({})
        ): INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
        vol.Optional(
            CONF_EXCLUDE, default=INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER({})
        ): INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
    }
)

INCLUDE_EXCLUDE_FILTER_SCHEMA = vol.All(
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA, convert_include_exclude_filter
)


def _glob_to_re(glob: str) -> re.Pattern[str]:
    """Translate and compile glob string into pattern."""
    return re.compile(fnmatch.translate(glob))


def _test_against_patterns(patterns: list[re.Pattern[str]], entity_id: str) -> bool:
    """Test entity against list of patterns, true if any match."""
    for pattern in patterns:
        if pattern.match(entity_id):
            return True

    return False


# It's safe since we don't modify it. And None causes typing warnings
# pylint: disable=dangerous-default-value
def generate_filter(
    include_domains: list[str],
    include_entities: list[str],
    exclude_domains: list[str],
    exclude_entities: list[str],
    include_entity_globs: list[str] = [],
    exclude_entity_globs: list[str] = [],
) -> Callable[[str], bool]:
    """Return a function that will filter entities based on the args."""
    include_d = set(include_domains)
    include_e = set(include_entities)
    exclude_d = set(exclude_domains)
    exclude_e = set(exclude_entities)
    include_eg_set = set(include_entity_globs)
    exclude_eg_set = set(exclude_entity_globs)
    include_eg = list(map(_glob_to_re, include_eg_set))
    exclude_eg = list(map(_glob_to_re, exclude_eg_set))

    have_exclude = bool(exclude_e or exclude_d or exclude_eg)
    have_include = bool(include_e or include_d or include_eg)

    def entity_included(domain: str, entity_id: str) -> bool:
        """Return true if entity matches inclusion filters."""
        return (
            entity_id in include_e
            or domain in include_d
            or bool(include_eg and _test_against_patterns(include_eg, entity_id))
        )

    def entity_excluded(domain: str, entity_id: str) -> bool:
        """Return true if entity matches exclusion filters."""
        return (
            entity_id in exclude_e
            or domain in exclude_d
            or bool(exclude_eg and _test_against_patterns(exclude_eg, entity_id))
        )

    # Case 1 - no includes or excludes - pass all entities
    if not have_include and not have_exclude:
        return lambda entity_id: True

    # Case 2 - includes, no excludes - only include specified entities
    if have_include and not have_exclude:

        def entity_filter_2(entity_id: str) -> bool:
            """Return filter function for case 2."""
            domain = split_entity_id(entity_id)[0]
            return entity_included(domain, entity_id)

        return entity_filter_2

    # Case 3 - excludes, no includes - only exclude specified entities
    if not have_include and have_exclude:

        def entity_filter_3(entity_id: str) -> bool:
            """Return filter function for case 3."""
            domain = split_entity_id(entity_id)[0]
            return not entity_excluded(domain, entity_id)

        return entity_filter_3

    # Case 4 - both includes and excludes specified
    # Case 4a - include domain or glob specified
    #  - if domain is included, pass if entity not excluded
    #  - if glob is included, pass if entity and domain not excluded
    #  - if domain and glob are not included, pass if entity is included
    # note: if both include domain matches then exclude domains ignored.
    #   If glob matches then exclude domains and glob checked
    if include_d or include_eg:

        def entity_filter_4a(entity_id: str) -> bool:
            """Return filter function for case 4a."""
            domain = split_entity_id(entity_id)[0]
            if domain in include_d:
                return not (
                    entity_id in exclude_e
                    or bool(
                        exclude_eg and _test_against_patterns(exclude_eg, entity_id)
                    )
                )
            if _test_against_patterns(include_eg, entity_id):
                return not entity_excluded(domain, entity_id)
            return entity_id in include_e

        return entity_filter_4a

    # Case 4b - exclude domain or glob specified, include has no domain or glob
    # In this one case the traditional include logic is inverted. Even though an
    # include is specified since its only a list of entity IDs its used only to
    # expose specific entities excluded by domain or glob. Any entities not
    # excluded are then presumed included. Logic is as follows
    #  - if domain or glob is excluded, pass if entity is included
    #  - if domain is not excluded, pass if entity not excluded by ID
    if exclude_d or exclude_eg:

        def entity_filter_4b(entity_id: str) -> bool:
            """Return filter function for case 4b."""
            domain = split_entity_id(entity_id)[0]
            if domain in exclude_d or (
                exclude_eg and _test_against_patterns(exclude_eg, entity_id)
            ):
                return entity_id in include_e
            return entity_id not in exclude_e

        return entity_filter_4b

    # Case 4c - neither include or exclude domain specified
    #  - Only pass if entity is included.  Ignore entity excludes.
    return lambda entity_id: entity_id in include_e

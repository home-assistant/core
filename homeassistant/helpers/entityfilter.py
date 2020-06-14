"""Helper class to implement include/exclude of entities and domains."""
import fnmatch
import re
from typing import Callable, Dict, List

import voluptuous as vol

from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import split_entity_id
from homeassistant.helpers import config_validation as cv

CONF_INCLUDE_DOMAINS = "include_domains"
CONF_INCLUDE_ENTITIES_GLOB = "include_entities_glob"
CONF_INCLUDE_ENTITIES = "include_entities"
CONF_EXCLUDE_DOMAINS = "exclude_domains"
CONF_EXCLUDE_ENTITIES_GLOB = "exclude_entities_glob"
CONF_EXCLUDE_ENTITIES = "exclude_entities"

CONF_ENTITIES_GLOB = "entities_glob"


def convert_filter(config: Dict[str, List[str]]) -> Callable[[str], bool]:
    """Convert the filter schema into a filter."""
    filt = generate_filter(
        config[CONF_INCLUDE_DOMAINS],
        config[CONF_INCLUDE_ENTITIES],
        config[CONF_EXCLUDE_DOMAINS],
        config[CONF_EXCLUDE_ENTITIES],
        config.get(CONF_INCLUDE_ENTITIES_GLOB, []),
        config.get(CONF_EXCLUDE_ENTITIES_GLOB, []),
    )
    setattr(filt, "config", config)
    setattr(filt, "empty_filter", sum(len(val) for val in config.values()) == 0)
    return filt


BASE_FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EXCLUDE_DOMAINS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EXCLUDE_ENTITIES_GLOB, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EXCLUDE_ENTITIES, default=[]): cv.entity_ids,
        vol.Optional(CONF_INCLUDE_DOMAINS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_INCLUDE_ENTITIES_GLOB, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_INCLUDE_ENTITIES, default=[]): cv.entity_ids,
    }
)

FILTER_SCHEMA = vol.All(BASE_FILTER_SCHEMA, convert_filter)


def convert_filter_alt(
    config: Dict[str, Dict[str, List[str]]]
) -> Callable[[str], bool]:
    """Convert the alternate filter schema into a filter."""
    include = config.get(CONF_INCLUDE, {})
    exclude = config.get(CONF_EXCLUDE, {})
    filt = generate_filter(
        include.get(CONF_DOMAINS, []),
        include.get(CONF_ENTITIES, []),
        exclude.get(CONF_DOMAINS, []),
        exclude.get(CONF_ENTITIES, []),
        include.get(CONF_ENTITIES_GLOB, []),
        exclude.get(CONF_ENTITIES_GLOB, []),
    )
    total_filters = sum(len(val) for val in include.values()) + sum(
        len(val) for val in exclude.values()
    )
    setattr(filt, "config", config)
    setattr(filt, "empty_filter", total_filters == 0)
    return filt


ALT_FILTER_SCHEMA_INNER = vol.Schema(
    {
        vol.Optional(CONF_DOMAINS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ENTITIES_GLOB, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
    }
)

ALT_BASE_FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_INCLUDE, default=ALT_FILTER_SCHEMA_INNER({})
        ): ALT_FILTER_SCHEMA_INNER,
        vol.Optional(
            CONF_EXCLUDE, default=ALT_FILTER_SCHEMA_INNER({})
        ): ALT_FILTER_SCHEMA_INNER,
    }
)

ALT_FILTER_SCHEMA = vol.All(ALT_BASE_FILTER_SCHEMA, convert_filter_alt)


# It's safe since we don't modify it. And None causes typing warnings
# pylint: disable=dangerous-default-value
def generate_filter(
    include_domains: List[str],
    include_entities: List[str],
    exclude_domains: List[str],
    exclude_entities: List[str],
    include_entities_glob: List[str] = [],
    exclude_entities_glob: List[str] = [],
) -> Callable[[str], bool]:
    """Return a function that will filter entities based on the args."""
    include_d = set(include_domains)
    include_e = set(include_entities)
    exclude_d = set(exclude_domains)
    exclude_e = set(exclude_entities)
    has_include_eg = bool(include_entities_glob)
    has_exclude_eg = bool(exclude_entities_glob)

    if has_include_eg:
        include_eg_re = "|".join(map(fnmatch.translate, include_entities_glob))
        include_eg = re.compile(f"^(?:{include_eg_re})$")

    if has_exclude_eg:
        exclude_eg_re = "|".join(map(fnmatch.translate, exclude_entities_glob))
        exclude_eg = re.compile(f"^(?:{exclude_eg_re})$")

    have_exclude = bool(exclude_e or exclude_d or has_exclude_eg)
    have_include = bool(include_e or include_d or has_include_eg)

    def entity_included(domain: str, entity_id: str) -> bool:
        """Return true if entity matches inclusion filters."""
        return bool(
            entity_id in include_e
            or domain in include_d
            or has_include_eg
            and include_eg.match(entity_id)
        )

    def entity_excluded(domain: str, entity_id: str) -> bool:
        """Return true if entity matches exclusion filters."""
        return bool(
            entity_id in exclude_e
            or domain in exclude_d
            or has_exclude_eg
            and exclude_eg.match(entity_id)
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
            if entity_id in include_e:
                return True

            domain = split_entity_id(entity_id)[0]
            if domain in include_d:
                return not (
                    entity_id in exclude_e
                    or has_exclude_eg
                    and exclude_eg.match(entity_id)
                )
            if include_eg and include_eg.match(entity_id):
                return not entity_excluded(domain, entity_id)

            return False

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
            if domain in exclude_d or exclude_eg and exclude_eg.match(entity_id):
                return entity_id in include_e
            return entity_id not in exclude_e

        return entity_filter_4b

    # Case 4c - neither include or exclude domain specified
    #  - Only pass if entity is included.  Ignore entity excludes.
    return lambda entity_id: entity_id in include_e

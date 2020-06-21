"""Helper class to implement include/exclude of entities and domains."""
from typing import Callable, Dict, List

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.helpers import config_validation as cv

CONF_INCLUDE_DOMAINS = "include_domains"
CONF_INCLUDE_ENTITIES = "include_entities"
CONF_EXCLUDE_DOMAINS = "exclude_domains"
CONF_EXCLUDE_ENTITIES = "exclude_entities"


def convert_filter(config: Dict[str, List[str]]) -> Callable[[str], bool]:
    """Convert the filter schema into a filter."""
    filt = generate_filter(
        config[CONF_INCLUDE_DOMAINS],
        config[CONF_INCLUDE_ENTITIES],
        config[CONF_EXCLUDE_DOMAINS],
        config[CONF_EXCLUDE_ENTITIES],
    )
    setattr(filt, "config", config)
    setattr(filt, "empty_filter", sum(len(val) for val in config.values()) == 0)
    return filt


BASE_FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EXCLUDE_DOMAINS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EXCLUDE_ENTITIES, default=[]): cv.entity_ids,
        vol.Optional(CONF_INCLUDE_DOMAINS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_INCLUDE_ENTITIES, default=[]): cv.entity_ids,
    }
)

FILTER_SCHEMA = vol.All(BASE_FILTER_SCHEMA, convert_filter)


def generate_filter(
    include_domains: List[str],
    include_entities: List[str],
    exclude_domains: List[str],
    exclude_entities: List[str],
) -> Callable[[str], bool]:
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
            return entity_id in include_e or domain in include_d

        return entity_filter_2

    # Case 3 - excludes, no includes - only exclude specified entities
    if not have_include and have_exclude:

        def entity_filter_3(entity_id: str) -> bool:
            """Return filter function for case 3."""
            domain = split_entity_id(entity_id)[0]
            return entity_id not in exclude_e and domain not in exclude_d

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

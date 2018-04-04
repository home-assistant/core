"""Helper class to implement include/exclude of entities, domains, and platforms."""

import voluptuous as vol

from homeassistant.core import split_entity_id
from homeassistant.helpers import config_validation as cv

CONF_INCLUDE_DOMAINS = 'include_domains'
CONF_INCLUDE_ENTITIES = 'include_entities'
CONF_EXCLUDE_DOMAINS = 'exclude_domains'
CONF_EXCLUDE_ENTITIES = 'exclude_entities'
CONF_INCLUDE_PLATFORMS = 'include_platforms'
CONF_EXCLUDE_PLATFORMS = 'exclude_platforms'

FILTER_SCHEMA = vol.All(
    vol.Schema({
        vol.Optional(CONF_EXCLUDE_DOMAINS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXCLUDE_ENTITIES, default=[]): cv.entity_ids,
        vol.Optional(CONF_EXCLUDE_PLATFORMS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_INCLUDE_DOMAINS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_INCLUDE_ENTITIES, default=[]): cv.entity_ids,
        vol.Optional(CONF_INCLUDE_PLATFORMS, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    }),
    lambda config: generate_filter(
        config[CONF_INCLUDE_DOMAINS],
        config[CONF_INCLUDE_ENTITIES],
        config[CONF_INCLUDE_PLATFORMS],
        config[CONF_EXCLUDE_DOMAINS],
        config[CONF_EXCLUDE_ENTITIES],
        config[CONF_EXCLUDE_PLATFORMS],
    ))


def generate_filter(include_domains, include_entities, include_platforms,
                    exclude_domains, exclude_entities, exclude_platforms):
    """Return a function that will filter entities based on the args."""
    include_d = set(include_domains)
    include_e = set(include_entities)
    include_p = set(include_platforms)
    exclude_d = set(exclude_domains)
    exclude_e = set(exclude_entities)
    exclude_p = set(exclude_platforms)

    have_exclude = bool(exclude_e or exclude_d or exclude_p)
    have_include = bool(include_e or include_d or include_p)

    # Case 1 - no includes or excludes - pass all entities
    if not have_include and not have_exclude:
        return lambda entity_id, entity_platform=None: True

    # Case 2 - includes, no excludes - only include specified entities/domains/platforms
    if have_include and not have_exclude:
        def entity_filter_2(entity_id, entity_platform=None):
            """Return filter function for case 2."""
            domain = split_entity_id(entity_id)[0]
            return (entity_id in include_e or
                    domain in include_d or
                    entity_platform in include_p)

        return entity_filter_2

    # Case 3 - excludes, no includes - only exclude specified entities/domains/platforms
    if not have_include and have_exclude:
        def entity_filter_3(entity_id, entity_platform=None):
            """Return filter function for case 3."""
            domain = split_entity_id(entity_id)[0]
            return (entity_id not in exclude_e and
                    domain not in exclude_d and
                    entity_platform not in exclude_p)

        return entity_filter_3

    # Case 4 - both includes and excludes specified
    # Case 4a - include platform specified
    #  - if platform is included, and domain and entity not excluded, pass
    #  - if platform is not included, and entity or domain not included, fail
    # note: if both include and exclude platform specified,
    #   the exclude platforms are ignored
    if include_p:
        def entity_filter_4a(entity_id, entity_platform=None):
            """Return filter function for case 4a."""
            domain = split_entity_id(entity_id)[0]
            if entity_platform in include_p:
                return (entity_id not in exclude_e and
                        domain not in exclude_d)
            return (entity_id not in include_e or
                    domain not in include_d)

        return entity_filter_4a

    # Case 4b - exclude platform specified
    #  - if platform is excluded, and entity not included, fail
    #  - if platform is not excluded:
    #        and entity is included,
    #        or the domain is included but the entity is neither, pass
    if exclude_p:
        def entity_filter_4b(entity_id, entity_platform=None):
            """Return filter function for case 4b."""
            domain = split_entity_id(entity_id)[0]
            if entity_platform in exclude_p:
                return entity_id in include_e
            return (entity_id in include_e or
                    (entity_id not in exclude_e and domain in include_d))

        return entity_filter_4b

    # Case 4c - include domain specified
    #  - if domain is included, and entity not excluded, pass
    #  - if domain is not included, and entity not included, fail
    # note: if both include and exclude domains specified,
    #   the exclude domains are ignored
    if include_d:
        def entity_filter_4c(entity_id, entity_platform=None):
            """Return filter function for case 4a."""
            domain = split_entity_id(entity_id)[0]
            if domain in include_d:
                return entity_id not in exclude_e
            return entity_id in include_e

        return entity_filter_4c

    # Case 4d - exclude domain specified
    #  - if domain is excluded, and entity not included, fail
    #  - if domain is not excluded, and entity not excluded, pass
    if exclude_d:
        def entity_filter_4d(entity_id, entity_platform=None):
            """Return filter function for case 4b."""
            domain = split_entity_id(entity_id)[0]
            if domain in exclude_d:
                return entity_id in include_e
            return entity_id not in exclude_e

        return entity_filter_4d

    # Case 4e - neither include or exclude platform or domain specified
    #  - Only pass if entity is included.  Ignore entity excludes.
    def entity_filter_4e(entity_id, entity_platform=None):
        """Return filter function for case 4c."""
        return entity_id in include_e

    return entity_filter_4e

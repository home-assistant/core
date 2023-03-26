"""Helper class to implement include/exclude of entities and domains."""
from __future__ import annotations

from collections.abc import Callable
import fnmatch
import re

import voluptuous as vol

from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import split_entity_id

from . import config_validation as cv

CONF_INCLUDE_DOMAINS = "include_domains"
CONF_INCLUDE_ENTITY_GLOBS = "include_entity_globs"
CONF_INCLUDE_ENTITIES = "include_entities"
CONF_EXCLUDE_DOMAINS = "exclude_domains"
CONF_EXCLUDE_ENTITY_GLOBS = "exclude_entity_globs"
CONF_EXCLUDE_ENTITIES = "exclude_entities"

CONF_ENTITY_GLOBS = "entity_globs"


class EntityFilter:
    """A entity filter."""

    def __init__(self, config: dict[str, list[str]]) -> None:
        """Init the filter."""
        self.empty_filter: bool = sum(len(val) for val in config.values()) == 0
        self.config = config
        self._include_e = set(config[CONF_INCLUDE_ENTITIES])
        self._exclude_e = set(config[CONF_EXCLUDE_ENTITIES])
        self._include_d = set(config[CONF_INCLUDE_DOMAINS])
        self._exclude_d = set(config[CONF_EXCLUDE_DOMAINS])
        self._include_eg = _convert_globs_to_pattern_list(
            config[CONF_INCLUDE_ENTITY_GLOBS]
        )
        self._exclude_eg = _convert_globs_to_pattern_list(
            config[CONF_EXCLUDE_ENTITY_GLOBS]
        )
        self._filter: Callable[[str], bool] | None = None

    def explicitly_included(self, entity_id: str) -> bool:
        """Check if an entity is explicitly included."""
        return entity_id in self._include_e or (
            bool(self._include_eg)
            and _test_against_patterns(self._include_eg, entity_id)
        )

    def explicitly_excluded(self, entity_id: str) -> bool:
        """Check if an entity is explicitly excluded."""
        return entity_id in self._exclude_e or (
            bool(self._exclude_eg)
            and _test_against_patterns(self._exclude_eg, entity_id)
        )

    def __call__(self, entity_id: str) -> bool:
        """Run the filter."""
        if self._filter is None:
            self._filter = _generate_filter_from_sets_and_pattern_lists(
                self._include_d,
                self._include_e,
                self._exclude_d,
                self._exclude_e,
                self._include_eg,
                self._exclude_eg,
            )
        return self._filter(entity_id)


def convert_filter(config: dict[str, list[str]]) -> EntityFilter:
    """Convert the filter schema into a filter."""
    return EntityFilter(config)


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
) -> EntityFilter:
    """Convert the include exclude filter schema into a filter."""
    include = config[CONF_INCLUDE]
    exclude = config[CONF_EXCLUDE]
    return convert_filter(
        {
            CONF_INCLUDE_DOMAINS: include[CONF_DOMAINS],
            CONF_INCLUDE_ENTITY_GLOBS: include[CONF_ENTITY_GLOBS],
            CONF_INCLUDE_ENTITIES: include[CONF_ENTITIES],
            CONF_EXCLUDE_DOMAINS: exclude[CONF_DOMAINS],
            CONF_EXCLUDE_ENTITY_GLOBS: exclude[CONF_ENTITY_GLOBS],
            CONF_EXCLUDE_ENTITIES: exclude[CONF_ENTITIES],
        }
    )


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
    return any(pattern.match(entity_id) for pattern in patterns)


def _convert_globs_to_pattern_list(globs: list[str] | None) -> list[re.Pattern[str]]:
    """Convert a list of globs to a re pattern list."""
    return list(map(_glob_to_re, set(globs or [])))


def generate_filter(
    include_domains: list[str],
    include_entities: list[str],
    exclude_domains: list[str],
    exclude_entities: list[str],
    include_entity_globs: list[str] | None = None,
    exclude_entity_globs: list[str] | None = None,
) -> Callable[[str], bool]:
    """Return a function that will filter entities based on the args."""
    return _generate_filter_from_sets_and_pattern_lists(
        set(include_domains),
        set(include_entities),
        set(exclude_domains),
        set(exclude_entities),
        _convert_globs_to_pattern_list(include_entity_globs),
        _convert_globs_to_pattern_list(exclude_entity_globs),
    )


def _generate_filter_from_sets_and_pattern_lists(
    include_d: set[str],
    include_e: set[str],
    exclude_d: set[str],
    exclude_e: set[str],
    include_eg: list[re.Pattern[str]],
    exclude_eg: list[re.Pattern[str]],
) -> Callable[[str], bool]:
    """Generate a filter from pre-comuted sets and pattern lists."""
    have_exclude = bool(exclude_e or exclude_d or exclude_eg)
    have_include = bool(include_e or include_d or include_eg)

    def entity_included(domain: str, entity_id: str) -> bool:
        """Return true if entity matches inclusion filters."""
        return (
            entity_id in include_e
            or domain in include_d
            or (bool(include_eg) and _test_against_patterns(include_eg, entity_id))
        )

    def entity_excluded(domain: str, entity_id: str) -> bool:
        """Return true if entity matches exclusion filters."""
        return (
            entity_id in exclude_e
            or domain in exclude_d
            or (bool(exclude_eg) and _test_against_patterns(exclude_eg, entity_id))
        )

    # Case 1 - No filter
    # - All entities included
    if not have_include and not have_exclude:
        return lambda entity_id: True

    # Case 2 - Only includes
    # - Entity listed in entities include: include
    # - Otherwise, entity matches domain include: include
    # - Otherwise, entity matches glob include: include
    # - Otherwise: exclude
    if have_include and not have_exclude:

        def entity_filter_2(entity_id: str) -> bool:
            """Return filter function for case 2."""
            domain = split_entity_id(entity_id)[0]
            return entity_included(domain, entity_id)

        return entity_filter_2

    # Case 3 - Only excludes
    # - Entity listed in exclude: exclude
    # - Otherwise, entity matches domain exclude: exclude
    # - Otherwise, entity matches glob exclude: exclude
    # - Otherwise: include
    if not have_include and have_exclude:

        def entity_filter_3(entity_id: str) -> bool:
            """Return filter function for case 3."""
            domain = split_entity_id(entity_id)[0]
            return not entity_excluded(domain, entity_id)

        return entity_filter_3

    # Case 4 - Domain and/or glob includes (may also have excludes)
    # - Entity listed in entities include: include
    # - Otherwise, entity listed in entities exclude: exclude
    # - Otherwise, entity matches glob include: include
    # - Otherwise, entity matches glob exclude: exclude
    # - Otherwise, entity matches domain include: include
    # - Otherwise: exclude
    if include_d or include_eg:

        def entity_filter_4a(entity_id: str) -> bool:
            """Return filter function for case 4a."""
            return entity_id in include_e or (
                entity_id not in exclude_e
                and (
                    (include_eg and _test_against_patterns(include_eg, entity_id))
                    or (
                        split_entity_id(entity_id)[0] in include_d
                        and not (
                            exclude_eg and _test_against_patterns(exclude_eg, entity_id)
                        )
                    )
                )
            )

        return entity_filter_4a

    # Case 5 - Domain and/or glob excludes (no domain and/or glob includes)
    # - Entity listed in entities include: include
    # - Otherwise, entity listed in exclude: exclude
    # - Otherwise, entity matches glob exclude: exclude
    # - Otherwise, entity matches domain exclude: exclude
    # - Otherwise: include
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

    # Case 6 - No Domain and/or glob includes or excludes
    # - Entity listed in entities include: include
    # - Otherwise: exclude
    return lambda entity_id: entity_id in include_e

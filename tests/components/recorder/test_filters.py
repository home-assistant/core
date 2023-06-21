"""The tests for recorder filters."""

import pytest

from homeassistant.components.recorder.filters import (
    Filters,
    extract_include_exclude_filter_conf,
    merge_include_exclude_filters,
)
from homeassistant.helpers.entityfilter import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_ENTITY_GLOBS,
    CONF_EXCLUDE,
    CONF_INCLUDE,
)

EMPTY_INCLUDE_FILTER = {
    CONF_INCLUDE: {
        CONF_DOMAINS: None,
        CONF_ENTITIES: None,
        CONF_ENTITY_GLOBS: None,
    }
}
SIMPLE_INCLUDE_FILTER = {
    CONF_INCLUDE: {
        CONF_DOMAINS: ["homeassistant"],
        CONF_ENTITIES: ["sensor.one"],
        CONF_ENTITY_GLOBS: ["climate.*"],
    }
}
SIMPLE_INCLUDE_FILTER_DIFFERENT_ENTITIES = {
    CONF_INCLUDE: {
        CONF_DOMAINS: ["other"],
        CONF_ENTITIES: ["not_sensor.one"],
        CONF_ENTITY_GLOBS: ["not_climate.*"],
    }
}
SIMPLE_EXCLUDE_FILTER = {
    CONF_EXCLUDE: {
        CONF_DOMAINS: ["homeassistant"],
        CONF_ENTITIES: ["sensor.one"],
        CONF_ENTITY_GLOBS: ["climate.*"],
    }
}
SIMPLE_INCLUDE_EXCLUDE_FILTER = {**SIMPLE_INCLUDE_FILTER, **SIMPLE_EXCLUDE_FILTER}


def test_extract_include_exclude_filter_conf() -> None:
    """Test we can extract a filter from configuration without altering it."""
    include_filter = extract_include_exclude_filter_conf(SIMPLE_INCLUDE_FILTER)
    assert include_filter == {
        CONF_EXCLUDE: {
            CONF_DOMAINS: set(),
            CONF_ENTITIES: set(),
            CONF_ENTITY_GLOBS: set(),
        },
        CONF_INCLUDE: {
            CONF_DOMAINS: {"homeassistant"},
            CONF_ENTITIES: {"sensor.one"},
            CONF_ENTITY_GLOBS: {"climate.*"},
        },
    }

    exclude_filter = extract_include_exclude_filter_conf(SIMPLE_EXCLUDE_FILTER)
    assert exclude_filter == {
        CONF_INCLUDE: {
            CONF_DOMAINS: set(),
            CONF_ENTITIES: set(),
            CONF_ENTITY_GLOBS: set(),
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: {"homeassistant"},
            CONF_ENTITIES: {"sensor.one"},
            CONF_ENTITY_GLOBS: {"climate.*"},
        },
    }

    include_exclude_filter = extract_include_exclude_filter_conf(
        SIMPLE_INCLUDE_EXCLUDE_FILTER
    )
    assert include_exclude_filter == {
        CONF_INCLUDE: {
            CONF_DOMAINS: {"homeassistant"},
            CONF_ENTITIES: {"sensor.one"},
            CONF_ENTITY_GLOBS: {"climate.*"},
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: {"homeassistant"},
            CONF_ENTITIES: {"sensor.one"},
            CONF_ENTITY_GLOBS: {"climate.*"},
        },
    }

    include_exclude_filter[CONF_EXCLUDE][CONF_ENTITIES] = {"cover.altered"}
    # verify it really is a copy
    assert SIMPLE_INCLUDE_EXCLUDE_FILTER[CONF_EXCLUDE][CONF_ENTITIES] != {
        "cover.altered"
    }
    empty_include_filter = extract_include_exclude_filter_conf(EMPTY_INCLUDE_FILTER)
    assert empty_include_filter == {
        CONF_EXCLUDE: {
            CONF_DOMAINS: set(),
            CONF_ENTITIES: set(),
            CONF_ENTITY_GLOBS: set(),
        },
        CONF_INCLUDE: {
            CONF_DOMAINS: set(),
            CONF_ENTITIES: set(),
            CONF_ENTITY_GLOBS: set(),
        },
    }


def test_merge_include_exclude_filters() -> None:
    """Test we can merge two filters together."""
    include_exclude_filter_base = extract_include_exclude_filter_conf(
        SIMPLE_INCLUDE_EXCLUDE_FILTER
    )
    include_filter_add = extract_include_exclude_filter_conf(
        SIMPLE_INCLUDE_FILTER_DIFFERENT_ENTITIES
    )
    merged_filter = merge_include_exclude_filters(
        include_exclude_filter_base, include_filter_add
    )
    assert merged_filter == {
        CONF_EXCLUDE: {
            CONF_DOMAINS: {"homeassistant"},
            CONF_ENTITIES: {"sensor.one"},
            CONF_ENTITY_GLOBS: {"climate.*"},
        },
        CONF_INCLUDE: {
            CONF_DOMAINS: {"other", "homeassistant"},
            CONF_ENTITIES: {"not_sensor.one", "sensor.one"},
            CONF_ENTITY_GLOBS: {"climate.*", "not_climate.*"},
        },
    }


async def test_an_empty_filter_raises() -> None:
    """Test empty filter raises when not guarding with has_config."""
    filters = Filters()
    assert not filters.has_config
    with pytest.raises(
        RuntimeError,
        match="No filter configuration provided, check has_config before calling this method",
    ):
        filters.states_metadata_entity_filter()
    with pytest.raises(
        RuntimeError,
        match="No filter configuration provided, check has_config before calling this method",
    ):
        filters.states_entity_filter()
    with pytest.raises(
        RuntimeError,
        match="No filter configuration provided, check has_config before calling this method",
    ):
        filters.events_entity_filter()

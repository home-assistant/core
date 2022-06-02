"""The tests for the recorder filter matching the EntityFilter component."""

from homeassistant.components.recorder.filters import (
    sqlalchemy_filter_from_include_exclude_conf,
)
from homeassistant.helpers.entityfilter import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_ENTITY_GLOBS,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    convert_include_exclude_filter,
)


async def test_included_and_excluded():
    """Test filters with included and excluded."""
    conf = {
        CONF_INCLUDE: {
            CONF_DOMAINS: ["light"],
            CONF_ENTITY_GLOBS: ["sensor.kitchen_*"],
            CONF_ENTITIES: ["switch.kitchen"],
        },
        CONF_EXCLUDE: {
            CONF_DOMAINS: ["cover"],
            CONF_ENTITY_GLOBS: ["sensor.weather_*"],
            CONF_ENTITIES: ["light.kitchen"],
        },
    }
    entity_filter = convert_include_exclude_filter(conf)
    sqlalchemy_filter = sqlalchemy_filter_from_include_exclude_conf(conf)
    assert sqlalchemy_filter is not None

    assert entity_filter("light.any") is True
    assert entity_filter("switch.other") is True
    assert entity_filter("sensor.kitchen_4") is True
    assert entity_filter("switch.kitchen") is True
    assert entity_filter("cover.any") is False
    assert entity_filter("sensor.weather_5") is False
    assert entity_filter("light.kitchen") is False

    assert not entity_filter.explicitly_included("light.any")
    assert not entity_filter.explicitly_included("switch.other")
    assert entity_filter.explicitly_included("sensor.kitchen_4")
    assert entity_filter.explicitly_included("switch.kitchen")

    assert not entity_filter.explicitly_excluded("light.any")
    assert not entity_filter.explicitly_excluded("switch.other")
    assert entity_filter.explicitly_excluded("sensor.weather_5")
    assert entity_filter.explicitly_excluded("light.kitchen")

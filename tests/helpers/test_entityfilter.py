"""The tests for the EntityFilter component."""
from homeassistant.helpers.entityfilter import (
    FILTER_SCHEMA,
    INCLUDE_EXCLUDE_FILTER_SCHEMA,
    generate_filter,
)


def test_no_filters_case_1():
    """If include and exclude not included, pass everything."""
    incl_dom = {}
    incl_ent = {}
    excl_dom = {}
    excl_ent = {}
    testfilter = generate_filter(incl_dom, incl_ent, excl_dom, excl_ent)

    for value in ("sensor.test", "sun.sun", "light.test"):
        assert testfilter(value)


def test_includes_only_case_2():
    """If include specified, only pass if specified (Case 2)."""
    incl_dom = {"light", "sensor"}
    incl_ent = {"binary_sensor.working"}
    excl_dom = {}
    excl_ent = {}
    testfilter = generate_filter(incl_dom, incl_ent, excl_dom, excl_ent)

    assert testfilter("sensor.test")
    assert testfilter("light.test")
    assert testfilter("binary_sensor.working")
    assert testfilter("binary_sensor.notworking") is False
    assert testfilter("sun.sun") is False


def test_includes_only_with_glob_case_2():
    """If include specified, only pass if specified (Case 2)."""
    incl_dom = {"light", "sensor"}
    incl_glob = {"cover.*_window"}
    incl_ent = {"binary_sensor.working"}
    excl_dom = {}
    excl_glob = {}
    excl_ent = {}
    testfilter = generate_filter(
        incl_dom, incl_ent, excl_dom, excl_ent, incl_glob, excl_glob
    )

    assert testfilter("sensor.test")
    assert testfilter("light.test")
    assert testfilter("cover.bedroom_window")
    assert testfilter("binary_sensor.working")
    assert testfilter("binary_sensor.notworking") is False
    assert testfilter("sun.sun") is False
    assert testfilter("cover.garage_door") is False


def test_excludes_only_case_3():
    """If exclude specified, pass all but specified (Case 3)."""
    incl_dom = {}
    incl_ent = {}
    excl_dom = {"light", "sensor"}
    excl_ent = {"binary_sensor.working"}
    testfilter = generate_filter(incl_dom, incl_ent, excl_dom, excl_ent)

    assert testfilter("sensor.test") is False
    assert testfilter("light.test") is False
    assert testfilter("binary_sensor.working") is False
    assert testfilter("binary_sensor.another")
    assert testfilter("sun.sun") is True


def test_excludes_only_with_glob_case_3():
    """If exclude specified, pass all but specified (Case 3)."""
    incl_dom = {}
    incl_glob = {}
    incl_ent = {}
    excl_dom = {"light", "sensor"}
    excl_glob = {"cover.*_window"}
    excl_ent = {"binary_sensor.working"}
    testfilter = generate_filter(
        incl_dom, incl_ent, excl_dom, excl_ent, incl_glob, excl_glob
    )

    assert testfilter("sensor.test") is False
    assert testfilter("light.test") is False
    assert testfilter("cover.bedroom_window") is False
    assert testfilter("binary_sensor.working") is False
    assert testfilter("binary_sensor.another")
    assert testfilter("sun.sun") is True
    assert testfilter("cover.garage_door")


def test_with_include_domain_case4a():
    """Test case 4a - include and exclude specified, with included domain."""
    incl_dom = {"light", "sensor"}
    incl_ent = {"binary_sensor.working"}
    excl_dom = {}
    excl_ent = {"light.ignoreme", "sensor.notworking"}
    testfilter = generate_filter(incl_dom, incl_ent, excl_dom, excl_ent)

    assert testfilter("sensor.test")
    assert testfilter("sensor.notworking") is False
    assert testfilter("light.test")
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.working")
    assert testfilter("binary_sensor.another") is False
    assert testfilter("sun.sun") is False


def test_with_include_glob_case4a():
    """Test case 4a - include and exclude specified, with included glob."""
    incl_dom = {}
    incl_glob = {"light.*", "sensor.*"}
    incl_ent = {"binary_sensor.working"}
    excl_dom = {}
    excl_glob = {}
    excl_ent = {"light.ignoreme", "sensor.notworking"}
    testfilter = generate_filter(
        incl_dom, incl_ent, excl_dom, excl_ent, incl_glob, excl_glob
    )

    assert testfilter("sensor.test")
    assert testfilter("sensor.notworking") is False
    assert testfilter("light.test")
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.working")
    assert testfilter("binary_sensor.another") is False
    assert testfilter("sun.sun") is False


def test_with_include_domain_glob_filtering_case4a():
    """Test case 4a - include and exclude specified, both have domains and globs."""
    incl_dom = {"light"}
    incl_glob = {"*working"}
    incl_ent = {}
    excl_dom = {"binary_sensor"}
    excl_glob = {"*notworking"}
    excl_ent = {"light.ignoreme"}
    testfilter = generate_filter(
        incl_dom, incl_ent, excl_dom, excl_ent, incl_glob, excl_glob
    )

    assert testfilter("sensor.working")
    assert testfilter("sensor.notworking") is False
    assert testfilter("light.test")
    assert testfilter("light.notworking") is False
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.not_working") is False
    assert testfilter("binary_sensor.another") is False
    assert testfilter("sun.sun") is False


def test_exclude_domain_case4b():
    """Test case 4b - include and exclude specified, with excluded domain."""
    incl_dom = {}
    incl_ent = {"binary_sensor.working"}
    excl_dom = {"binary_sensor"}
    excl_ent = {"light.ignoreme", "sensor.notworking"}
    testfilter = generate_filter(incl_dom, incl_ent, excl_dom, excl_ent)

    assert testfilter("sensor.test")
    assert testfilter("sensor.notworking") is False
    assert testfilter("light.test")
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.working")
    assert testfilter("binary_sensor.another") is False
    assert testfilter("sun.sun") is True


def test_exclude_glob_case4b():
    """Test case 4b - include and exclude specified, with excluded glob."""
    incl_dom = {}
    incl_glob = {}
    incl_ent = {"binary_sensor.working"}
    excl_dom = {}
    excl_glob = {"binary_sensor.*"}
    excl_ent = {"light.ignoreme", "sensor.notworking"}
    testfilter = generate_filter(
        incl_dom, incl_ent, excl_dom, excl_ent, incl_glob, excl_glob
    )

    assert testfilter("sensor.test")
    assert testfilter("sensor.notworking") is False
    assert testfilter("light.test")
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.working")
    assert testfilter("binary_sensor.another") is False
    assert testfilter("sun.sun") is True


def test_no_domain_case4c():
    """Test case 4c - include and exclude specified, with no domains."""
    incl_dom = {}
    incl_ent = {"binary_sensor.working"}
    excl_dom = {}
    excl_ent = {"light.ignoreme", "sensor.notworking"}
    testfilter = generate_filter(incl_dom, incl_ent, excl_dom, excl_ent)

    assert testfilter("sensor.test") is False
    assert testfilter("sensor.notworking") is False
    assert testfilter("light.test") is False
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.working")
    assert testfilter("binary_sensor.another") is False
    assert testfilter("sun.sun") is False


def test_filter_schema():
    """Test filter schema."""
    conf = {
        "include_domains": ["light"],
        "include_entities": ["switch.kitchen"],
        "exclude_domains": ["cover"],
        "exclude_entities": ["light.kitchen"],
    }
    filt = FILTER_SCHEMA(conf)
    conf.update({"include_entity_globs": [], "exclude_entity_globs": []})
    assert filt.config == conf


def test_filter_schema_with_globs():
    """Test filter schema with glob options."""
    conf = {
        "include_domains": ["light"],
        "include_entity_globs": ["sensor.kitchen_*"],
        "include_entities": ["switch.kitchen"],
        "exclude_domains": ["cover"],
        "exclude_entity_globs": ["sensor.weather_*"],
        "exclude_entities": ["light.kitchen"],
    }
    filt = FILTER_SCHEMA(conf)
    assert filt.config == conf


def test_filter_schema_include_exclude():
    """Test the include exclude filter schema."""
    conf = {
        "include": {
            "domains": ["light"],
            "entity_globs": ["sensor.kitchen_*"],
            "entities": ["switch.kitchen"],
        },
        "exclude": {
            "domains": ["cover"],
            "entity_globs": ["sensor.weather_*"],
            "entities": ["light.kitchen"],
        },
    }
    filt = INCLUDE_EXCLUDE_FILTER_SCHEMA(conf)
    assert filt.config == conf

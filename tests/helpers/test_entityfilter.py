"""The tests for the EntityFilter component."""
from homeassistant.helpers.entityfilter import FILTER_SCHEMA, generate_filter


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
    assert filt.config == conf

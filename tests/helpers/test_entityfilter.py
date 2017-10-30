"""The tests for the EntityFitler component."""
from homeassistant.helpers.entityfilter import EntityFilter


def test_no_filters_case_1():
    """If include and exclude not included, pass everything."""
    include_filter = {}
    exclude_filter = {}
    testfilter = EntityFilter(include_filter, exclude_filter)

    for value in ("sensor.test", "sun.sun", "light.test"):
        assert testfilter.check_entity(value)


def test_includes_only_case_2():
    """If include specified, only pass if specified (Case 2)."""
    include_filter = {
        'domains': [
            'light',
            'sensor'
        ],
        'entities': [
            'binary_sensor.working'
        ]
    }
    exclude_filter = {}
    testfilter = EntityFilter(include_filter, exclude_filter)

    assert testfilter.check_entity("sensor.test")
    assert testfilter.check_entity("light.test")
    assert testfilter.check_entity("binary_sensor.working")
    assert testfilter.check_entity("binary_sensor.notworking") is False
    assert testfilter.check_entity("sun.sun") is False


def test_excludes_only_case_3():
    """If exclude specified, pass all but specified (Case 3)."""
    exclude_filter = {
        'domains': [
            'light',
            'sensor'
        ],
        'entities': [
            'binary_sensor.working'
        ]
    }
    include_filter = {}
    testfilter = EntityFilter(include_filter, exclude_filter)

    assert testfilter.check_entity("sensor.test") is False
    assert testfilter.check_entity("light.test") is False
    assert testfilter.check_entity("binary_sensor.working") is False
    assert testfilter.check_entity("binary_sensor.another")
    assert testfilter.check_entity("sun.sun") is True


def test_with_include_domain_case4a():
    """Test case 4a - include and exclude specified, with included domain."""
    include_filter = {
        'domains': [
            'light',
            'sensor'
        ],
        'entities': [
            'binary_sensor.working'
        ]
    }
    exclude_filter = {
        'entities': [
            'light.ignoreme',
            'sensor.notworking'
        ]
    }
    testfilter = EntityFilter(include_filter, exclude_filter)

    assert testfilter.check_entity("sensor.test")
    assert testfilter.check_entity("sensor.notworking") is False
    assert testfilter.check_entity("light.test")
    assert testfilter.check_entity("light.ignoreme") is False
    assert testfilter.check_entity("binary_sensor.working")
    assert testfilter.check_entity("binary_sensor.another") is False
    assert testfilter.check_entity("sun.sun") is False


def test_exclude_domain_case4b():
    """Test case 4b - include and exclude specified, with excluded domain."""
    include_filter = {
        'entities': [
            'binary_sensor.working'
        ]
    }
    exclude_filter = {
        'domains': [
            'binary_sensor'
        ],
        'entities': [
            'light.ignoreme',
            'sensor.notworking'
        ]
    }
    testfilter = EntityFilter(include_filter, exclude_filter)

    assert testfilter.check_entity("sensor.test")
    assert testfilter.check_entity("sensor.notworking") is False
    assert testfilter.check_entity("light.test")
    assert testfilter.check_entity("light.ignoreme") is False
    assert testfilter.check_entity("binary_sensor.working")
    assert testfilter.check_entity("binary_sensor.another") is False
    assert testfilter.check_entity("sun.sun") is True


def testno_domain_case4c():
    """Test case 4c - include and exclude specified, with no domains."""
    include_filter = {
        'entities': [
            'binary_sensor.working'
        ]
    }
    exclude_filter = {
        'entities': [
            'light.ignoreme',
            'sensor.notworking'
        ]
    }
    testfilter = EntityFilter(include_filter, exclude_filter)

    assert testfilter.check_entity("sensor.test") is False
    assert testfilter.check_entity("sensor.notworking") is False
    assert testfilter.check_entity("light.test") is False
    assert testfilter.check_entity("light.ignoreme") is False
    assert testfilter.check_entity("binary_sensor.working")
    assert testfilter.check_entity("binary_sensor.another") is False
    assert testfilter.check_entity("sun.sun") is False

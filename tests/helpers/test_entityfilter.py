"""The tests for the EntityFilter component."""

from homeassistant.helpers.entityfilter import (
    FILTER_SCHEMA,
    INCLUDE_EXCLUDE_FILTER_SCHEMA,
    EntityFilter,
    generate_filter,
)


def test_no_filters_case_1() -> None:
    """If include and exclude not included, pass everything."""
    incl_dom = {}
    incl_ent = {}
    excl_dom = {}
    excl_ent = {}
    testfilter = generate_filter(incl_dom, incl_ent, excl_dom, excl_ent)

    for value in ("sensor.test", "sun.sun", "light.test"):
        assert testfilter(value)


def test_includes_only_case_2() -> None:
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


def test_includes_only_with_glob_case_2() -> None:
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


def test_excludes_only_case_3() -> None:
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


def test_excludes_only_with_glob_case_3() -> None:
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


def test_with_include_domain_case4() -> None:
    """Test case 4 - include and exclude specified, with included domain."""
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


def test_with_include_domain_exclude_glob_case4() -> None:
    """Test case 4 - include and exclude specified, with included domain but excluded by glob."""
    incl_dom = {"light", "sensor"}
    incl_ent = {"binary_sensor.working"}
    incl_glob = {}
    excl_dom = {}
    excl_ent = {"light.ignoreme", "sensor.notworking"}
    excl_glob = {"sensor.busted"}
    testfilter = generate_filter(
        incl_dom, incl_ent, excl_dom, excl_ent, incl_glob, excl_glob
    )

    assert testfilter("sensor.test")
    assert testfilter("sensor.busted") is False
    assert testfilter("sensor.notworking") is False
    assert testfilter("light.test")
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.working")
    assert testfilter("binary_sensor.another") is False
    assert testfilter("sun.sun") is False


def test_with_include_glob_case4() -> None:
    """Test case 4 - include and exclude specified, with included glob."""
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


def test_with_include_domain_glob_filtering_case4() -> None:
    """Test case 4 - include and exclude specified, both have domains and globs."""
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
    assert testfilter("sensor.notworking") is True  # include is stronger
    assert testfilter("light.test")
    assert testfilter("light.notworking") is True  # include is stronger
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.not_working") is True  # include is stronger
    assert testfilter("binary_sensor.another") is False
    assert testfilter("sun.sun") is False


def test_with_include_domain_glob_filtering_case4a_include_strong() -> None:
    """Test case 4 - include and exclude specified, both have domains and globs, and a specifically included entity."""
    incl_dom = {"light"}
    incl_glob = {"*working"}
    incl_ent = {"binary_sensor.specificly_included"}
    excl_dom = {"binary_sensor"}
    excl_glob = {"*notworking"}
    excl_ent = {"light.ignoreme"}
    testfilter = generate_filter(
        incl_dom, incl_ent, excl_dom, excl_ent, incl_glob, excl_glob
    )

    assert testfilter("sensor.working")
    assert testfilter("sensor.notworking") is True  # include is stronger
    assert testfilter("light.test")
    assert testfilter("light.notworking") is True  # include is stronger
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.not_working") is True  # include is stronger
    assert testfilter("binary_sensor.another") is False
    assert testfilter("binary_sensor.specificly_included") is True
    assert testfilter("sun.sun") is False


def test_with_include_glob_filtering_case4a_include_strong() -> None:
    """Test case 4 - include and exclude specified, both have globs, and a specifically included entity."""
    incl_dom = {}
    incl_glob = {"*working"}
    incl_ent = {"binary_sensor.specificly_included"}
    excl_dom = {}
    excl_glob = {"*broken", "*notworking", "binary_sensor.*"}
    excl_ent = {"light.ignoreme"}
    testfilter = generate_filter(
        incl_dom, incl_ent, excl_dom, excl_ent, incl_glob, excl_glob
    )

    assert testfilter("sensor.working") is True
    assert testfilter("sensor.notworking") is True  # include is stronger
    assert testfilter("sensor.broken") is False
    assert testfilter("light.test") is False
    assert testfilter("light.notworking") is True  # include is stronger
    assert testfilter("light.ignoreme") is False
    assert testfilter("binary_sensor.not_working") is True  # include is stronger
    assert testfilter("binary_sensor.another") is False
    assert testfilter("binary_sensor.specificly_included") is True
    assert testfilter("sun.sun") is False


def test_exclude_domain_case5() -> None:
    """Test case 5 - include and exclude specified, with excluded domain."""
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


def test_exclude_glob_case5() -> None:
    """Test case 5 - include and exclude specified, with excluded glob."""
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


def test_exclude_glob_case5_include_strong() -> None:
    """Test case 5 - include and exclude specified, with excluded glob, and a specifically included entity."""
    incl_dom = {}
    incl_glob = {}
    incl_ent = {"binary_sensor.working"}
    excl_dom = {"binary_sensor"}
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


def test_no_domain_case6() -> None:
    """Test case 6 - include and exclude specified, with no domains."""
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


def test_filter_schema_empty() -> None:
    """Test filter schema."""
    conf = {}
    filt = FILTER_SCHEMA(conf)
    conf.update(
        {
            "include_domains": [],
            "include_entities": [],
            "exclude_domains": [],
            "exclude_entities": [],
            "include_entity_globs": [],
            "exclude_entity_globs": [],
        }
    )
    assert filt.config == conf
    assert filt.empty_filter


def test_filter_schema() -> None:
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
    assert not filt.empty_filter


def test_filter_schema_with_globs() -> None:
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
    assert not filt.empty_filter


def test_filter_schema_include_exclude() -> None:
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
    assert filt.config == {
        "include_domains": ["light"],
        "include_entity_globs": ["sensor.kitchen_*"],
        "include_entities": ["switch.kitchen"],
        "exclude_domains": ["cover"],
        "exclude_entity_globs": ["sensor.weather_*"],
        "exclude_entities": ["light.kitchen"],
    }
    assert not filt.empty_filter


def test_explicitly_included() -> None:
    """Test if an entity is explicitly included."""
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
    filt: EntityFilter = INCLUDE_EXCLUDE_FILTER_SCHEMA(conf)
    assert not filt.explicitly_included("light.any")
    assert not filt.explicitly_included("switch.other")
    assert filt.explicitly_included("sensor.kitchen_4")
    assert filt.explicitly_included("switch.kitchen")

    assert not filt.explicitly_excluded("light.any")
    assert not filt.explicitly_excluded("switch.other")
    assert filt.explicitly_excluded("sensor.weather_5")
    assert filt.explicitly_excluded("light.kitchen")


def test_get_filter() -> None:
    """Test we can get the underlying filter."""
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
    filt: EntityFilter = INCLUDE_EXCLUDE_FILTER_SCHEMA(conf)
    underlying_filter = filt.get_filter()
    assert underlying_filter("light.any")
    assert not underlying_filter("switch.other")
    assert underlying_filter("sensor.kitchen_4")
    assert underlying_filter("switch.kitchen")


def test_complex_include_exclude_filter() -> None:
    """Test a complex include exclude filter."""
    conf = {
        "include": {
            "domains": ["switch", "person"],
            "entities": ["group.family"],
            "entity_globs": [
                "sensor.*_sensor_temperature",
                "sensor.*_actueel",
                "sensor.*_totaal",
                "sensor.calculated*",
                "sensor.solaredge_*",
                "sensor.speedtest*",
                "sensor.teller*",
                "sensor.zp*",
                "binary_sensor.*_sensor_motion",
                "binary_sensor.*_door",
                "sensor.water_*ly",
                "sensor.gas_*ly",
            ],
        },
        "exclude": {
            "domains": [
                "alarm_control_panel",
                "alert",
                "automation",
                "button",
                "camera",
                "climate",
                "counter",
                "cover",
                "geo_location",
                "group",
                "input_boolean",
                "input_datetime",
                "input_number",
                "input_select",
                "input_text",
                "light",
                "media_player",
                "number",
                "proximity",
                "remote",
                "scene",
                "script",
                "sun",
                "timer",
                "updater",
                "variable",
                "weather",
                "zone",
            ],
            "entities": [
                "sensor.solaredge_last_updatetime",
                "sensor.solaredge_last_changed",
            ],
            "entity_globs": ["switch.*_light_level", "switch.sonos_*"],
        },
    }
    filt: EntityFilter = INCLUDE_EXCLUDE_FILTER_SCHEMA(conf)
    assert filt("switch.espresso_keuken") is True

"""Test Home Assistant template helper methods."""
from datetime import datetime
import math
import random
from unittest.mock import patch

import pytest
import pytz
import voluptuous as vol

from homeassistant.components import group
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    LENGTH_METERS,
    MASS_GRAMS,
    PRESSURE_PA,
    TEMP_CELSIUS,
    VOLUME_LITERS,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import UnitSystem

from tests.common import MockConfigEntry, mock_device_registry, mock_registry


def _set_up_units(hass):
    """Set up the tests."""
    hass.config.units = UnitSystem(
        "custom", TEMP_CELSIUS, LENGTH_METERS, VOLUME_LITERS, MASS_GRAMS, PRESSURE_PA
    )


def render_to_info(hass, template_str, variables=None):
    """Create render info from template."""
    tmp = template.Template(template_str, hass)
    return tmp.async_render_to_info(variables)


def extract_entities(hass, template_str, variables=None):
    """Extract entities from a template."""
    info = render_to_info(hass, template_str, variables)
    return info.entities


def assert_result_info(info, result, entities=None, domains=None, all_states=False):
    """Check result info."""
    assert info.result() == result
    assert info.all_states == all_states
    assert info.filter("invalid_entity_name.somewhere") == all_states
    if entities is not None:
        assert info.entities == frozenset(entities)
        assert all([info.filter(entity) for entity in entities])
        if not all_states:
            assert not info.filter("invalid_entity_name.somewhere")
    else:
        assert not info.entities
    if domains is not None:
        assert info.domains == frozenset(domains)
        assert all([info.filter(domain + ".entity") for domain in domains])
    else:
        assert not hasattr(info, "_domains")


def test_template_equality():
    """Test template comparison and hashing."""
    template_one = template.Template("{{ template_one }}")
    template_one_1 = template.Template("{{ template_one }}")
    template_two = template.Template("{{ template_two }}")

    assert template_one == template_one_1
    assert template_one != template_two
    assert hash(template_one) == hash(template_one_1)
    assert hash(template_one) != hash(template_two)

    assert str(template_one_1) == 'Template("{{ template_one }}")'

    with pytest.raises(TypeError):
        template.Template(["{{ template_one }}"])


def test_invalid_template(hass):
    """Invalid template raises error."""
    tmpl = template.Template("{{", hass)

    with pytest.raises(TemplateError):
        tmpl.ensure_valid()

    with pytest.raises(TemplateError):
        tmpl.async_render()

    info = tmpl.async_render_to_info()
    with pytest.raises(TemplateError):
        assert info.result() == "impossible"

    tmpl = template.Template("{{states(keyword)}}", hass)

    tmpl.ensure_valid()

    with pytest.raises(TemplateError):
        tmpl.async_render()


def test_referring_states_by_entity_id(hass):
    """Test referring states by entity id."""
    hass.states.async_set("test.object", "happy")
    assert (
        template.Template("{{ states.test.object.state }}", hass).async_render()
        == "happy"
    )

    assert (
        template.Template('{{ states["test.object"].state }}', hass).async_render()
        == "happy"
    )

    assert (
        template.Template('{{ states("test.object") }}', hass).async_render() == "happy"
    )


def test_invalid_entity_id(hass):
    """Test referring states by entity id."""
    with pytest.raises(TemplateError):
        template.Template('{{ states["big.fat..."] }}', hass).async_render()
    with pytest.raises(TemplateError):
        template.Template('{{ states.test["big.fat..."] }}', hass).async_render()
    with pytest.raises(TemplateError):
        template.Template('{{ states["invalid/domain"] }}', hass).async_render()


def test_raise_exception_on_error(hass):
    """Test raising an exception on error."""
    with pytest.raises(TemplateError):
        template.Template("{{ invalid_syntax").ensure_valid()


def test_iterating_all_states(hass):
    """Test iterating all states."""
    tmpl_str = "{% for state in states %}{{ state.state }}{% endfor %}"

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "", all_states=True)
    assert info.rate_limit == template.ALL_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "happy")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "10happy", entities=[], all_states=True)


def test_iterating_all_states_unavailable(hass):
    """Test iterating all states unavailable."""
    hass.states.async_set("test.object", "on")

    tmpl_str = "{{ states | selectattr('state', 'in', ['unavailable', 'unknown', 'none']) | list | count }}"

    info = render_to_info(hass, tmpl_str)

    assert info.all_states is True
    assert info.rate_limit == template.ALL_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "unknown")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, 1, entities=[], all_states=True)


def test_iterating_domain_states(hass):
    """Test iterating domain states."""
    tmpl_str = "{% for state in states.sensor %}{{ state.state }}{% endfor %}"

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "", domains=["sensor"])
    assert info.rate_limit == template.DOMAIN_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "happy")
    hass.states.async_set("sensor.back_door", "open")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(
        info,
        "open10",
        entities=[],
        domains=["sensor"],
    )


def test_float(hass):
    """Test float."""
    hass.states.async_set("sensor.temperature", "12")

    assert (
        template.Template(
            "{{ float(states.sensor.temperature.state) }}", hass
        ).async_render()
        == 12.0
    )

    assert (
        template.Template(
            "{{ float(states.sensor.temperature.state) > 11 }}", hass
        ).async_render()
        is True
    )

    assert (
        template.Template("{{ float('forgiving') }}", hass).async_render()
        == "forgiving"
    )


def test_rounding_value(hass):
    """Test rounding value."""
    hass.states.async_set("sensor.temperature", 12.78)

    assert (
        template.Template(
            "{{ states.sensor.temperature.state | round(1) }}", hass
        ).async_render()
        == 12.8
    )

    assert (
        template.Template(
            "{{ states.sensor.temperature.state | multiply(10) | round }}", hass
        ).async_render()
        == 128
    )

    assert (
        template.Template(
            '{{ states.sensor.temperature.state | round(1, "floor") }}', hass
        ).async_render()
        == 12.7
    )

    assert (
        template.Template(
            '{{ states.sensor.temperature.state | round(1, "ceil") }}', hass
        ).async_render()
        == 12.8
    )

    assert (
        template.Template(
            '{{ states.sensor.temperature.state | round(1, "half") }}', hass
        ).async_render()
        == 13.0
    )


def test_rounding_value_get_original_value_on_error(hass):
    """Test rounding value get original value on error."""
    assert template.Template("{{ None | round }}", hass).async_render() is None

    assert (
        template.Template('{{ "no_number" | round }}', hass).async_render()
        == "no_number"
    )


def test_multiply(hass):
    """Test multiply."""
    tests = {None: None, 10: 100, '"abcd"': "abcd"}

    for inp, out in tests.items():
        assert (
            template.Template(
                "{{ %s | multiply(10) | round }}" % inp, hass
            ).async_render()
            == out
        )


def test_logarithm(hass):
    """Test logarithm."""
    tests = [
        (4, 2, 2.0),
        (1000, 10, 3.0),
        (math.e, "", 1.0),
        ('"invalid"', "_", "invalid"),
        (10, '"invalid"', 10.0),
    ]

    for value, base, expected in tests:
        assert (
            template.Template(
                f"{{{{ {value} | log({base}) | round(1) }}}}", hass
            ).async_render()
            == expected
        )

        assert (
            template.Template(
                f"{{{{ log({value}, {base}) | round(1) }}}}", hass
            ).async_render()
            == expected
        )


def test_sine(hass):
    """Test sine."""
    tests = [
        (0, 0.0),
        (math.pi / 2, 1.0),
        (math.pi, 0.0),
        (math.pi * 1.5, -1.0),
        (math.pi / 10, 0.309),
        ('"duck"', "duck"),
    ]

    for value, expected in tests:
        assert (
            template.Template("{{ %s | sin | round(3) }}" % value, hass).async_render()
            == expected
        )


def test_cos(hass):
    """Test cosine."""
    tests = [
        (0, 1.0),
        (math.pi / 2, 0.0),
        (math.pi, -1.0),
        (math.pi * 1.5, -0.0),
        (math.pi / 10, 0.951),
        ("'error'", "error"),
    ]

    for value, expected in tests:
        assert (
            template.Template("{{ %s | cos | round(3) }}" % value, hass).async_render()
            == expected
        )


def test_tan(hass):
    """Test tangent."""
    tests = [
        (0, 0.0),
        (math.pi, -0.0),
        (math.pi / 180 * 45, 1.0),
        (math.pi / 180 * 90, "1.633123935319537e+16"),
        (math.pi / 180 * 135, -1.0),
        ("'error'", "error"),
    ]

    for value, expected in tests:
        assert (
            template.Template("{{ %s | tan | round(3) }}" % value, hass).async_render()
            == expected
        )


def test_sqrt(hass):
    """Test square root."""
    tests = [
        (0, 0.0),
        (1, 1.0),
        (2, 1.414),
        (10, 3.162),
        (100, 10.0),
        ("'error'", "error"),
    ]

    for value, expected in tests:
        assert (
            template.Template("{{ %s | sqrt | round(3) }}" % value, hass).async_render()
            == expected
        )


def test_arc_sine(hass):
    """Test arcus sine."""
    tests = [
        (-2.0, -2.0),  # value error
        (-1.0, -1.571),
        (-0.5, -0.524),
        (0.0, 0.0),
        (0.5, 0.524),
        (1.0, 1.571),
        (2.0, 2.0),  # value error
        ('"error"', "error"),
    ]

    for value, expected in tests:
        assert (
            template.Template("{{ %s | asin | round(3) }}" % value, hass).async_render()
            == expected
        )


def test_arc_cos(hass):
    """Test arcus cosine."""
    tests = [
        (-2.0, -2.0),  # value error
        (-1.0, 3.142),
        (-0.5, 2.094),
        (0.0, 1.571),
        (0.5, 1.047),
        (1.0, 0.0),
        (2.0, 2.0),  # value error
        ('"error"', "error"),
    ]

    for value, expected in tests:
        assert (
            template.Template("{{ %s | acos | round(3) }}" % value, hass).async_render()
            == expected
        )


def test_arc_tan(hass):
    """Test arcus tangent."""
    tests = [
        (-10.0, -1.471),
        (-2.0, -1.107),
        (-1.0, -0.785),
        (-0.5, -0.464),
        (0.0, 0.0),
        (0.5, 0.464),
        (1.0, 0.785),
        (2.0, 1.107),
        (10.0, 1.471),
        ('"error"', "error"),
    ]

    for value, expected in tests:
        assert (
            template.Template("{{ %s | atan | round(3) }}" % value, hass).async_render()
            == expected
        )


def test_arc_tan2(hass):
    """Test two parameter version of arcus tangent."""
    tests = [
        (-10.0, -10.0, -2.356),
        (-10.0, 0.0, -1.571),
        (-10.0, 10.0, -0.785),
        (0.0, -10.0, 3.142),
        (0.0, 0.0, 0.0),
        (0.0, 10.0, 0.0),
        (10.0, -10.0, 2.356),
        (10.0, 0.0, 1.571),
        (10.0, 10.0, 0.785),
        (-4.0, 3.0, -0.927),
        (-1.0, 2.0, -0.464),
        (2.0, 1.0, 1.107),
        ('"duck"', '"goose"', ("duck", "goose")),
    ]

    for y, x, expected in tests:
        assert (
            template.Template(
                f"{{{{ ({y}, {x}) | atan2 | round(3) }}}}", hass
            ).async_render()
            == expected
        )
        assert (
            template.Template(
                f"{{{{ atan2({y}, {x}) | round(3) }}}}", hass
            ).async_render()
            == expected
        )


def test_strptime(hass):
    """Test the parse timestamp method."""
    tests = [
        ("2016-10-19 15:22:05.588122 UTC", "%Y-%m-%d %H:%M:%S.%f %Z", None),
        ("2016-10-19 15:22:05.588122+0100", "%Y-%m-%d %H:%M:%S.%f%z", None),
        ("2016-10-19 15:22:05.588122", "%Y-%m-%d %H:%M:%S.%f", None),
        ("2016-10-19", "%Y-%m-%d", None),
        ("2016", "%Y", None),
        ("15:22:05", "%H:%M:%S", None),
        ("1469119144", "%Y", 1469119144),
        ("invalid", "%Y", "invalid"),
    ]

    for inp, fmt, expected in tests:
        if expected is None:
            expected = str(datetime.strptime(inp, fmt))

        temp = f"{{{{ strptime('{inp}', '{fmt}') }}}}"

        assert template.Template(temp, hass).async_render() == expected


def test_timestamp_custom(hass):
    """Test the timestamps to custom filter."""
    now = dt_util.utcnow()
    tests = [
        (None, None, None, None),
        (1469119144, None, True, "2016-07-21 16:39:04"),
        (1469119144, "%Y", True, 2016),
        (1469119144, "invalid", True, "invalid"),
        (dt_util.as_timestamp(now), None, False, now.strftime("%Y-%m-%d %H:%M:%S")),
    ]

    for inp, fmt, local, out in tests:
        if fmt:
            fil = f"timestamp_custom('{fmt}')"
        elif fmt and local:
            fil = f"timestamp_custom('{fmt}', {local})"
        else:
            fil = "timestamp_custom"

        assert template.Template(f"{{{{ {inp} | {fil} }}}}", hass).async_render() == out


def test_timestamp_local(hass):
    """Test the timestamps to local filter."""
    tests = {None: None, 1469119144: "2016-07-21 16:39:04"}

    for inp, out in tests.items():
        assert (
            template.Template("{{ %s | timestamp_local }}" % inp, hass).async_render()
            == out
        )


def test_as_local(hass):
    """Test converting time to local."""

    hass.states.async_set("test.object", "available")
    last_updated = hass.states.get("test.object").last_updated
    assert template.Template(
        "{{ as_local(states.test.object.last_updated) }}", hass
    ).async_render() == str(dt_util.as_local(last_updated))
    assert template.Template(
        "{{ states.test.object.last_updated | as_local }}", hass
    ).async_render() == str(dt_util.as_local(last_updated))


def test_to_json(hass):
    """Test the object to JSON string filter."""

    # Note that we're not testing the actual json.loads and json.dumps methods,
    # only the filters, so we don't need to be exhaustive with our sample JSON.
    expected_result = {"Foo": "Bar"}
    actual_result = template.Template(
        "{{ {'Foo': 'Bar'} | to_json }}", hass
    ).async_render()
    assert actual_result == expected_result


def test_from_json(hass):
    """Test the JSON string to object filter."""

    # Note that we're not testing the actual json.loads and json.dumps methods,
    # only the filters, so we don't need to be exhaustive with our sample JSON.
    expected_result = "Bar"
    actual_result = template.Template(
        '{{ (\'{"Foo": "Bar"}\' | from_json).Foo }}', hass
    ).async_render()
    assert actual_result == expected_result


def test_min(hass):
    """Test the min filter."""
    assert template.Template("{{ [1, 2, 3] | min }}", hass).async_render() == 1
    assert template.Template("{{ min([1, 2, 3]) }}", hass).async_render() == 1
    assert template.Template("{{ min(1, 2, 3) }}", hass).async_render() == 1


def test_max(hass):
    """Test the max filter."""
    assert template.Template("{{ [1, 2, 3] | max }}", hass).async_render() == 3
    assert template.Template("{{ max([1, 2, 3]) }}", hass).async_render() == 3
    assert template.Template("{{ max(1, 2, 3) }}", hass).async_render() == 3


def test_ord(hass):
    """Test the ord filter."""
    assert template.Template('{{ "d" | ord }}', hass).async_render() == 100


def test_base64_encode(hass):
    """Test the base64_encode filter."""
    assert (
        template.Template('{{ "homeassistant" | base64_encode }}', hass).async_render()
        == "aG9tZWFzc2lzdGFudA=="
    )


def test_base64_decode(hass):
    """Test the base64_decode filter."""
    assert (
        template.Template(
            '{{ "aG9tZWFzc2lzdGFudA==" | base64_decode }}', hass
        ).async_render()
        == "homeassistant"
    )


def test_ordinal(hass):
    """Test the ordinal filter."""
    tests = [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (5, "5th"),
        (12, "12th"),
        (100, "100th"),
        (101, "101st"),
    ]

    for value, expected in tests:
        assert (
            template.Template("{{ %s | ordinal }}" % value, hass).async_render()
            == expected
        )


def test_timestamp_utc(hass):
    """Test the timestamps to local filter."""
    now = dt_util.utcnow()
    tests = {
        None: None,
        1469119144: "2016-07-21 16:39:04",
        dt_util.as_timestamp(now): now.strftime("%Y-%m-%d %H:%M:%S"),
    }

    for inp, out in tests.items():
        assert (
            template.Template("{{ %s | timestamp_utc }}" % inp, hass).async_render()
            == out
        )


def test_as_timestamp(hass):
    """Test the as_timestamp function."""
    assert (
        template.Template('{{ as_timestamp("invalid") }}', hass).async_render() is None
    )
    hass.mock = None
    assert (
        template.Template("{{ as_timestamp(states.mock) }}", hass).async_render()
        is None
    )

    tpl = (
        '{{ as_timestamp(strptime("2024-02-03T09:10:24+0000", '
        '"%Y-%m-%dT%H:%M:%S%z")) }}'
    )
    assert template.Template(tpl, hass).async_render() == 1706951424.0


@patch.object(random, "choice")
def test_random_every_time(test_choice, hass):
    """Ensure the random filter runs every time, not just once."""
    tpl = template.Template("{{ [1,2] | random }}", hass)
    test_choice.return_value = "foo"
    assert tpl.async_render() == "foo"
    test_choice.return_value = "bar"
    assert tpl.async_render() == "bar"


def test_passing_vars_as_keywords(hass):
    """Test passing variables as keywords."""
    assert template.Template("{{ hello }}", hass).async_render(hello=127) == 127


def test_passing_vars_as_vars(hass):
    """Test passing variables as variables."""
    assert template.Template("{{ hello }}", hass).async_render({"hello": 127}) == 127


def test_passing_vars_as_list(hass):
    """Test passing variables as list."""
    assert template.render_complex(
        template.Template("{{ hello }}", hass), {"hello": ["foo", "bar"]}
    ) == ["foo", "bar"]


def test_passing_vars_as_list_element(hass):
    """Test passing variables as list."""
    assert (
        template.render_complex(
            template.Template("{{ hello[1] }}", hass), {"hello": ["foo", "bar"]}
        )
        == "bar"
    )


def test_passing_vars_as_dict_element(hass):
    """Test passing variables as list."""
    assert (
        template.render_complex(
            template.Template("{{ hello.foo }}", hass), {"hello": {"foo": "bar"}}
        )
        == "bar"
    )


def test_passing_vars_as_dict(hass):
    """Test passing variables as list."""
    assert template.render_complex(
        template.Template("{{ hello }}", hass), {"hello": {"foo": "bar"}}
    ) == {"foo": "bar"}


def test_render_with_possible_json_value_with_valid_json(hass):
    """Render with possible JSON value with valid JSON."""
    tpl = template.Template("{{ value_json.hello }}", hass)
    assert tpl.async_render_with_possible_json_value('{"hello": "world"}') == "world"


def test_render_with_possible_json_value_with_invalid_json(hass):
    """Render with possible JSON value with invalid JSON."""
    tpl = template.Template("{{ value_json }}", hass)
    assert tpl.async_render_with_possible_json_value("{ I AM NOT JSON }") == ""


def test_render_with_possible_json_value_with_template_error_value(hass):
    """Render with possible JSON value with template error value."""
    tpl = template.Template("{{ non_existing.variable }}", hass)
    assert tpl.async_render_with_possible_json_value("hello", "-") == "-"


def test_render_with_possible_json_value_with_missing_json_value(hass):
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template("{{ value_json.goodbye }}", hass)
    assert tpl.async_render_with_possible_json_value('{"hello": "world"}') == ""


def test_render_with_possible_json_value_valid_with_is_defined(hass):
    """Render with possible JSON value with known JSON object."""
    tpl = template.Template("{{ value_json.hello|is_defined }}", hass)
    assert tpl.async_render_with_possible_json_value('{"hello": "world"}') == "world"


def test_render_with_possible_json_value_undefined_json(hass):
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template("{{ value_json.bye|is_defined }}", hass)
    assert (
        tpl.async_render_with_possible_json_value('{"hello": "world"}')
        == '{"hello": "world"}'
    )


def test_render_with_possible_json_value_undefined_json_error_value(hass):
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template("{{ value_json.bye|is_defined }}", hass)
    assert tpl.async_render_with_possible_json_value('{"hello": "world"}', "") == ""


def test_render_with_possible_json_value_non_string_value(hass):
    """Render with possible JSON value with non-string value."""
    tpl = template.Template(
        """
{{ strptime(value~'+0000', '%Y-%m-%d %H:%M:%S%z') }}
        """,
        hass,
    )
    value = datetime(2019, 1, 18, 12, 13, 14)
    expected = str(pytz.utc.localize(value))
    assert tpl.async_render_with_possible_json_value(value) == expected


def test_if_state_exists(hass):
    """Test if state exists works."""
    hass.states.async_set("test.object", "available")
    tpl = template.Template(
        "{% if states.test.object %}exists{% else %}not exists{% endif %}", hass
    )
    assert tpl.async_render() == "exists"


def test_is_state(hass):
    """Test is_state method."""
    hass.states.async_set("test.object", "available")
    tpl = template.Template(
        """
{% if is_state("test.object", "available") %}yes{% else %}no{% endif %}
        """,
        hass,
    )
    assert tpl.async_render() == "yes"

    tpl = template.Template(
        """
{{ is_state("test.noobject", "available") }}
        """,
        hass,
    )
    assert tpl.async_render() is False


def test_is_state_attr(hass):
    """Test is_state_attr method."""
    hass.states.async_set("test.object", "available", {"mode": "on"})
    tpl = template.Template(
        """
{% if is_state_attr("test.object", "mode", "on") %}yes{% else %}no{% endif %}
            """,
        hass,
    )
    assert tpl.async_render() == "yes"

    tpl = template.Template(
        """
{{ is_state_attr("test.noobject", "mode", "on") }}
            """,
        hass,
    )
    assert tpl.async_render() is False


def test_state_attr(hass):
    """Test state_attr method."""
    hass.states.async_set("test.object", "available", {"mode": "on"})
    tpl = template.Template(
        """
{% if state_attr("test.object", "mode") == "on" %}yes{% else %}no{% endif %}
            """,
        hass,
    )
    assert tpl.async_render() == "yes"

    tpl = template.Template(
        """
{{ state_attr("test.noobject", "mode") == None }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_states_function(hass):
    """Test using states as a function."""
    hass.states.async_set("test.object", "available")
    tpl = template.Template('{{ states("test.object") }}', hass)
    assert tpl.async_render() == "available"

    tpl2 = template.Template('{{ states("test.object2") }}', hass)
    assert tpl2.async_render() == "unknown"


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
def test_now(mock_is_safe, hass):
    """Test now method."""
    now = dt_util.now()
    with patch("homeassistant.util.dt.now", return_value=now):
        info = template.Template("{{ now().isoformat() }}", hass).async_render_to_info()
        assert now.isoformat() == info.result()

    assert info.has_time is True


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
def test_utcnow(mock_is_safe, hass):
    """Test now method."""
    utcnow = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow):
        info = template.Template(
            "{{ utcnow().isoformat() }}", hass
        ).async_render_to_info()
        assert utcnow.isoformat() == info.result()

    assert info.has_time is True


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
def test_relative_time(mock_is_safe, hass):
    """Test relative_time method."""
    now = datetime.strptime("2000-01-01 10:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
    with patch("homeassistant.util.dt.now", return_value=now):
        result = template.Template(
            '{{relative_time(strptime("2000-01-01 09:00:00", "%Y-%m-%d %H:%M:%S"))}}',
            hass,
        ).async_render()
        assert result == "1 hour"

        result = template.Template(
            '{{relative_time(strptime("2000-01-01 09:00:00 +01:00", "%Y-%m-%d %H:%M:%S %z"))}}',
            hass,
        ).async_render()
        assert result == "2 hours"

        result = template.Template(
            '{{relative_time(strptime("2000-01-01 03:00:00 -06:00", "%Y-%m-%d %H:%M:%S %z"))}}',
            hass,
        ).async_render()
        assert result == "1 hour"

        result1 = str(
            template.strptime("2000-01-01 11:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
        )
        result2 = template.Template(
            '{{relative_time(strptime("2000-01-01 11:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z"))}}',
            hass,
        ).async_render()
        assert result1 == result2

        result = template.Template(
            '{{relative_time("string")}}',
            hass,
        ).async_render()
        assert result == "string"


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
def test_timedelta(mock_is_safe, hass):
    """Test relative_time method."""
    now = datetime.strptime("2000-01-01 10:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
    with patch("homeassistant.util.dt.now", return_value=now):
        result = template.Template(
            "{{timedelta(seconds=120)}}",
            hass,
        ).async_render()
        assert result == "0:02:00"

        result = template.Template(
            "{{timedelta(seconds=86400)}}",
            hass,
        ).async_render()
        assert result == "1 day, 0:00:00"

        result = template.Template(
            "{{timedelta(days=1, hours=4)}}", hass
        ).async_render()
        assert result == "1 day, 4:00:00"

        result = template.Template(
            "{{relative_time(now() - timedelta(seconds=3600))}}",
            hass,
        ).async_render()
        assert result == "1 hour"

        result = template.Template(
            "{{relative_time(now() - timedelta(seconds=86400))}}",
            hass,
        ).async_render()
        assert result == "1 day"

        result = template.Template(
            "{{relative_time(now() - timedelta(seconds=86401))}}",
            hass,
        ).async_render()
        assert result == "1 day"

        result = template.Template(
            "{{relative_time(now() - timedelta(weeks=2, days=1))}}",
            hass,
        ).async_render()
        assert result == "15 days"


def test_regex_match(hass):
    """Test regex_match method."""
    tpl = template.Template(
        r"""
{{ '123-456-7890' | regex_match('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
{{ 'Home Assistant test' | regex_match('home', True) }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
    {{ 'Another Home Assistant test' | regex_match('Home') }}
                    """,
        hass,
    )
    assert tpl.async_render() is False

    tpl = template.Template(
        """
{{ ['Home Assistant test'] | regex_match('.*Assist') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_match_test(hass):
    """Test match test."""
    tpl = template.Template(
        r"""
{{ '123-456-7890' is match('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_regex_search(hass):
    """Test regex_search method."""
    tpl = template.Template(
        r"""
{{ '123-456-7890' | regex_search('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
{{ 'Home Assistant test' | regex_search('home', True) }}
            """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
    {{ 'Another Home Assistant test' | regex_search('Home') }}
                    """,
        hass,
    )
    assert tpl.async_render() is True

    tpl = template.Template(
        """
{{ ['Home Assistant test'] | regex_search('Assist') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_search_test(hass):
    """Test search test."""
    tpl = template.Template(
        r"""
{{ '123-456-7890' is search('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """,
        hass,
    )
    assert tpl.async_render() is True


def test_regex_replace(hass):
    """Test regex_replace method."""
    tpl = template.Template(
        r"""
{{ 'Hello World' | regex_replace('(Hello\\s)',) }}
            """,
        hass,
    )
    assert tpl.async_render() == "World"

    tpl = template.Template(
        """
{{ ['Home hinderant test'] | regex_replace('hinder', 'Assist') }}
            """,
        hass,
    )
    assert tpl.async_render() == ["Home Assistant test"]


def test_regex_findall_index(hass):
    """Test regex_findall_index method."""
    tpl = template.Template(
        """
{{ 'Flight from JFK to LHR' | regex_findall_index('([A-Z]{3})', 0) }}
            """,
        hass,
    )
    assert tpl.async_render() == "JFK"

    tpl = template.Template(
        """
{{ 'Flight from JFK to LHR' | regex_findall_index('([A-Z]{3})', 1) }}
            """,
        hass,
    )
    assert tpl.async_render() == "LHR"

    tpl = template.Template(
        """
{{ ['JFK', 'LHR'] | regex_findall_index('([A-Z]{3})', 1) }}
            """,
        hass,
    )
    assert tpl.async_render() == "LHR"


def test_bitwise_and(hass):
    """Test bitwise_and method."""
    tpl = template.Template(
        """
{{ 8 | bitwise_and(8) }}
            """,
        hass,
    )
    assert tpl.async_render() == 8 & 8
    tpl = template.Template(
        """
{{ 10 | bitwise_and(2) }}
            """,
        hass,
    )
    assert tpl.async_render() == 10 & 2
    tpl = template.Template(
        """
{{ 8 | bitwise_and(2) }}
            """,
        hass,
    )
    assert tpl.async_render() == 8 & 2


def test_bitwise_or(hass):
    """Test bitwise_or method."""
    tpl = template.Template(
        """
{{ 8 | bitwise_or(8) }}
            """,
        hass,
    )
    assert tpl.async_render() == 8 | 8
    tpl = template.Template(
        """
{{ 10 | bitwise_or(2) }}
            """,
        hass,
    )
    assert tpl.async_render() == 10 | 2
    tpl = template.Template(
        """
{{ 8 | bitwise_or(2) }}
            """,
        hass,
    )
    assert tpl.async_render() == 8 | 2


def test_distance_function_with_1_state(hass):
    """Test distance function with 1 state."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )
    tpl = template.Template("{{ distance(states.test.object) | round }}", hass)
    assert tpl.async_render() == 187


def test_distance_function_with_2_states(hass):
    """Test distance function with 2 states."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )
    tpl = template.Template(
        "{{ distance(states.test.object, states.test.object_2) | round }}", hass
    )
    assert tpl.async_render() == 187


def test_distance_function_with_1_coord(hass):
    """Test distance function with 1 coord."""
    _set_up_units(hass)
    tpl = template.Template('{{ distance("32.87336", "-117.22943") | round }}', hass)
    assert tpl.async_render() == 187


def test_distance_function_with_2_coords(hass):
    """Test distance function with 2 coords."""
    _set_up_units(hass)
    assert (
        template.Template(
            '{{ distance("32.87336", "-117.22943", %s, %s) | round }}'
            % (hass.config.latitude, hass.config.longitude),
            hass,
        ).async_render()
        == 187
    )


def test_distance_function_with_1_state_1_coord(hass):
    """Test distance function with 1 state 1 coord."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )
    tpl = template.Template(
        '{{ distance("32.87336", "-117.22943", states.test.object_2) ' "| round }}",
        hass,
    )
    assert tpl.async_render() == 187

    tpl2 = template.Template(
        '{{ distance(states.test.object_2, "32.87336", "-117.22943") ' "| round }}",
        hass,
    )
    assert tpl2.async_render() == 187


def test_distance_function_return_none_if_invalid_state(hass):
    """Test distance function return None if invalid state."""
    hass.states.async_set("test.object_2", "happy", {"latitude": 10})
    tpl = template.Template("{{ distance(states.test.object_2) | round }}", hass)
    assert tpl.async_render() is None


def test_distance_function_return_none_if_invalid_coord(hass):
    """Test distance function return None if invalid coord."""
    assert (
        template.Template('{{ distance("123", "abc") }}', hass).async_render() is None
    )

    assert template.Template('{{ distance("123") }}', hass).async_render() is None

    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )
    tpl = template.Template('{{ distance("123", states.test_object_2) }}', hass)
    assert tpl.async_render() is None


def test_distance_function_with_2_entity_ids(hass):
    """Test distance function with 2 entity ids."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )
    tpl = template.Template(
        '{{ distance("test.object", "test.object_2") | round }}', hass
    )
    assert tpl.async_render() == 187


def test_distance_function_with_1_entity_1_coord(hass):
    """Test distance function with 1 entity_id and 1 coord."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )
    tpl = template.Template(
        '{{ distance("test.object", "32.87336", "-117.22943") | round }}', hass
    )
    assert tpl.async_render() == 187


def test_closest_function_home_vs_domain(hass):
    """Test closest function home vs domain."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_test_domain.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert (
        template.Template(
            "{{ closest(states.test_domain).entity_id }}", hass
        ).async_render()
        == "test_domain.object"
    )

    assert (
        template.Template(
            "{{ (states.test_domain | closest).entity_id }}", hass
        ).async_render()
        == "test_domain.object"
    )


def test_closest_function_home_vs_all_states(hass):
    """Test closest function home vs all states."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain_2.and_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert (
        template.Template("{{ closest(states).entity_id }}", hass).async_render()
        == "test_domain_2.and_closer"
    )

    assert (
        template.Template("{{ (states | closest).entity_id }}", hass).async_render()
        == "test_domain_2.and_closer"
    )


async def test_closest_function_home_vs_group_entity_id(hass):
    """Test closest function home vs group entity id."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_in_group.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(hass, "location group", ["test_domain.object"])

    info = render_to_info(hass, '{{ closest("group.location_group").entity_id }}')
    assert_result_info(
        info, "test_domain.object", {"group.location_group", "test_domain.object"}
    )
    assert info.rate_limit is None


async def test_closest_function_home_vs_group_state(hass):
    """Test closest function home vs group state."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_in_group.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(hass, "location group", ["test_domain.object"])

    info = render_to_info(hass, '{{ closest("group.location_group").entity_id }}')
    assert_result_info(
        info, "test_domain.object", {"group.location_group", "test_domain.object"}
    )
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ closest(states.group.location_group).entity_id }}")
    assert_result_info(
        info, "test_domain.object", {"test_domain.object", "group.location_group"}
    )
    assert info.rate_limit is None


async def test_expand(hass):
    """Test expand function."""
    info = render_to_info(hass, "{{ expand('test.object') }}")
    assert_result_info(info, [], ["test.object"])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ expand(56) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    hass.states.async_set("test.object", "happy")

    info = render_to_info(
        hass, "{{ expand('test.object') | map(attribute='entity_id') | join(', ') }}"
    )
    assert_result_info(info, "test.object", ["test.object"])
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        "{{ expand('group.new_group') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "", ["group.new_group"])
    assert info.rate_limit is None

    info = render_to_info(
        hass, "{{ expand(states.group) | map(attribute='entity_id') | join(', ') }}"
    )
    assert_result_info(info, "", [], ["group"])
    assert info.rate_limit == template.DOMAIN_STATES_RATE_LIMIT

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(hass, "new group", ["test.object"])

    info = render_to_info(
        hass,
        "{{ expand('group.new_group') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", {"group.new_group", "test.object"})
    assert info.rate_limit is None

    info = render_to_info(
        hass, "{{ expand(states.group) | map(attribute='entity_id') | join(', ') }}"
    )
    assert_result_info(info, "test.object", {"test.object"}, ["group"])
    assert info.rate_limit == template.DOMAIN_STATES_RATE_LIMIT

    info = render_to_info(
        hass,
        "{{ expand('group.new_group', 'test.object')"
        " | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", {"test.object", "group.new_group"})

    info = render_to_info(
        hass,
        "{{ ['group.new_group', 'test.object'] | expand"
        " | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", {"test.object", "group.new_group"})
    assert info.rate_limit is None

    hass.states.async_set("sensor.power_1", 0)
    hass.states.async_set("sensor.power_2", 200.2)
    hass.states.async_set("sensor.power_3", 400.4)

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass, "power sensors", ["sensor.power_1", "sensor.power_2", "sensor.power_3"]
    )

    info = render_to_info(
        hass,
        "{{ states.group.power_sensors.attributes.entity_id | expand | map(attribute='state')|map('float')|sum  }}",
    )
    assert_result_info(
        info,
        200.2 + 400.4,
        {"group.power_sensors", "sensor.power_1", "sensor.power_2", "sensor.power_3"},
    )
    assert info.rate_limit is None


async def test_device_entities(hass):
    """Test expand function."""
    config_entry = MockConfigEntry(domain="light")
    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    # Test non existing device ids
    info = render_to_info(hass, "{{ device_entities('abc123') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ device_entities(56) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test device without entities
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={("mac", "12:34:56:AB:CD:EF")},
    )
    info = render_to_info(hass, f"{{{{ device_entities('{device_entry.id}') }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Test device with single entity, which has no state
    entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    info = render_to_info(hass, f"{{{{ device_entities('{device_entry.id}') }}}}")
    assert_result_info(info, ["light.hue_5678"], [])
    assert info.rate_limit is None
    info = render_to_info(
        hass,
        f"{{{{ device_entities('{device_entry.id}') | expand | map(attribute='entity_id') | join(', ') }}}}",
    )
    assert_result_info(info, "", ["light.hue_5678"])
    assert info.rate_limit is None

    # Test device with single entity, with state
    hass.states.async_set("light.hue_5678", "happy")
    info = render_to_info(
        hass,
        f"{{{{ device_entities('{device_entry.id}') | expand | map(attribute='entity_id') | join(', ') }}}}",
    )
    assert_result_info(info, "light.hue_5678", ["light.hue_5678"])
    assert info.rate_limit is None

    # Test device with multiple entities, which have a state
    entity_registry.async_get_or_create(
        "light",
        "hue",
        "ABCD",
        config_entry=config_entry,
        device_id=device_entry.id,
    )
    hass.states.async_set("light.hue_abcd", "camper")
    info = render_to_info(hass, f"{{{{ device_entities('{device_entry.id}') }}}}")
    assert_result_info(info, ["light.hue_5678", "light.hue_abcd"], [])
    assert info.rate_limit is None
    info = render_to_info(
        hass,
        f"{{{{ device_entities('{device_entry.id}') | expand | map(attribute='entity_id') | join(', ') }}}}",
    )
    assert_result_info(
        info, "light.hue_5678, light.hue_abcd", ["light.hue_5678", "light.hue_abcd"]
    )
    assert info.rate_limit is None


def test_closest_function_to_coord(hass):
    """Test closest function to coord."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    tpl = template.Template(
        '{{ closest("%s", %s, states.test_domain).entity_id }}'
        % (hass.config.latitude + 0.3, hass.config.longitude + 0.3),
        hass,
    )

    assert tpl.async_render() == "test_domain.closest_zone"

    tpl = template.Template(
        '{{ (states.test_domain | closest("%s", %s)).entity_id }}'
        % (hass.config.latitude + 0.3, hass.config.longitude + 0.3),
        hass,
    )

    assert tpl.async_render() == "test_domain.closest_zone"


def test_async_render_to_info_with_branching(hass):
    """Test async_render_to_info function by domain."""
    hass.states.async_set("light.a", "off")
    hass.states.async_set("light.b", "on")
    hass.states.async_set("light.c", "off")

    info = render_to_info(
        hass,
        """
{% if states.light.a == "on" %}
  {{ states.light.b.state }}
{% else %}
  {{ states.light.c.state }}
{% endif %}
""",
    )
    assert_result_info(info, "off", {"light.a", "light.c"})
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        """
            {% if states.light.a.state == "off" %}
            {% set domain = "light" %}
            {{ states[domain].b.state }}
            {% endif %}
""",
    )
    assert_result_info(info, "on", {"light.a", "light.b"})
    assert info.rate_limit is None


def test_async_render_to_info_with_complex_branching(hass):
    """Test async_render_to_info function by domain."""
    hass.states.async_set("light.a", "off")
    hass.states.async_set("light.b", "on")
    hass.states.async_set("light.c", "off")
    hass.states.async_set("vacuum.a", "off")
    hass.states.async_set("device_tracker.a", "off")
    hass.states.async_set("device_tracker.b", "off")
    hass.states.async_set("lock.a", "off")
    hass.states.async_set("sensor.a", "off")
    hass.states.async_set("binary_sensor.a", "off")

    info = render_to_info(
        hass,
        """
{% set domain = "vacuum" %}
{%      if                 states.light.a == "on" %}
  {{ states.light.b.state }}
{% elif  states.light.a == "on" %}
  {{ states.device_tracker }}
{%     elif     states.light.a == "on" %}
  {{ states[domain] | list }}
{%         elif     states('light.b') == "on" %}
  {{ states[otherdomain] | map(attribute='entity_id') | list }}
{% elif states.light.a == "on" %}
  {{ states["nonexist"] | list }}
{% else %}
  else
{% endif %}
""",
        {"otherdomain": "sensor"},
    )

    assert_result_info(info, ["sensor.a"], {"light.a", "light.b"}, {"sensor"})
    assert info.rate_limit == template.DOMAIN_STATES_RATE_LIMIT


async def test_async_render_to_info_with_wildcard_matching_entity_id(hass):
    """Test tracking template with a wildcard."""
    template_complex_str = r"""

{% for state in states.cover %}
  {% if state.entity_id | regex_match('.*\.office_') %}
    {{ state.entity_id }}={{ state.state }}
  {% endif %}
{% endfor %}

"""
    hass.states.async_set("cover.office_drapes", "closed")
    hass.states.async_set("cover.office_window", "closed")
    hass.states.async_set("cover.office_skylight", "open")
    info = render_to_info(hass, template_complex_str)

    assert info.domains == {"cover"}
    assert info.entities == set()
    assert info.all_states is False
    assert info.rate_limit == template.DOMAIN_STATES_RATE_LIMIT


async def test_async_render_to_info_with_wildcard_matching_state(hass):
    """Test tracking template with a wildcard."""
    template_complex_str = """

{% for state in states %}
  {% if state.state | regex_match('ope.*') %}
    {{ state.entity_id }}={{ state.state }}
  {% endif %}
{% endfor %}

"""
    hass.states.async_set("cover.office_drapes", "closed")
    hass.states.async_set("cover.office_window", "closed")
    hass.states.async_set("cover.office_skylight", "open")
    hass.states.async_set("cover.x_skylight", "open")
    hass.states.async_set("binary_sensor.door", "open")
    await hass.async_block_till_done()

    info = render_to_info(hass, template_complex_str)

    assert not info.domains
    assert info.entities == set()
    assert info.all_states is True
    assert info.rate_limit == template.ALL_STATES_RATE_LIMIT

    hass.states.async_set("binary_sensor.door", "closed")
    info = render_to_info(hass, template_complex_str)

    assert not info.domains
    assert info.entities == set()
    assert info.all_states is True
    assert info.rate_limit == template.ALL_STATES_RATE_LIMIT

    template_cover_str = """

{% for state in states.cover %}
  {% if state.state | regex_match('ope.*') %}
    {{ state.entity_id }}={{ state.state }}
  {% endif %}
{% endfor %}

"""
    hass.states.async_set("cover.x_skylight", "closed")
    info = render_to_info(hass, template_cover_str)

    assert info.domains == {"cover"}
    assert info.entities == set()
    assert info.all_states is False
    assert info.rate_limit == template.DOMAIN_STATES_RATE_LIMIT


def test_nested_async_render_to_info_case(hass):
    """Test a deeply nested state with async_render_to_info."""

    hass.states.async_set("input_select.picker", "vacuum.a")
    hass.states.async_set("vacuum.a", "off")

    info = render_to_info(
        hass, "{{ states[states['input_select.picker'].state].state }}", {}
    )
    assert_result_info(info, "off", {"input_select.picker", "vacuum.a"})
    assert info.rate_limit is None


def test_result_as_boolean(hass):
    """Test converting a template result to a boolean."""

    assert template.result_as_boolean(True) is True
    assert template.result_as_boolean(" 1 ") is True
    assert template.result_as_boolean(" true ") is True
    assert template.result_as_boolean(" TrUE ") is True
    assert template.result_as_boolean(" YeS ") is True
    assert template.result_as_boolean(" On ") is True
    assert template.result_as_boolean(" Enable ") is True
    assert template.result_as_boolean(1) is True
    assert template.result_as_boolean(-1) is True
    assert template.result_as_boolean(500) is True
    assert template.result_as_boolean(0.5) is True
    assert template.result_as_boolean(0.389) is True
    assert template.result_as_boolean(35) is True

    assert template.result_as_boolean(False) is False
    assert template.result_as_boolean(" 0 ") is False
    assert template.result_as_boolean(" false ") is False
    assert template.result_as_boolean(" FaLsE ") is False
    assert template.result_as_boolean(" no ") is False
    assert template.result_as_boolean(" off ") is False
    assert template.result_as_boolean(" disable ") is False
    assert template.result_as_boolean(0) is False
    assert template.result_as_boolean(0.0) is False
    assert template.result_as_boolean("0.00") is False
    assert template.result_as_boolean(None) is False


def test_closest_function_to_entity_id(hass):
    """Test closest function to entity id."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    info = render_to_info(
        hass,
        "{{ closest(zone, states.test_domain).entity_id }}",
        {"zone": "zone.far_away"},
    )

    assert_result_info(
        info,
        "test_domain.closest_zone",
        ["test_domain.closest_home", "test_domain.closest_zone", "zone.far_away"],
        ["test_domain"],
    )

    info = render_to_info(
        hass,
        "{{ ([states.test_domain, 'test_domain.closest_zone'] "
        "| closest(zone)).entity_id }}",
        {"zone": "zone.far_away"},
    )

    assert_result_info(
        info,
        "test_domain.closest_zone",
        ["test_domain.closest_home", "test_domain.closest_zone", "zone.far_away"],
        ["test_domain"],
    )


def test_closest_function_to_state(hass):
    """Test closest function to state."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    assert (
        template.Template(
            "{{ closest(states.zone.far_away, states.test_domain).entity_id }}", hass
        ).async_render()
        == "test_domain.closest_zone"
    )


def test_closest_function_invalid_state(hass):
    """Test closest function invalid state."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    for state in ("states.zone.non_existing", '"zone.non_existing"'):
        assert (
            template.Template("{{ closest(%s, states) }}" % state, hass).async_render()
            is None
        )


def test_closest_function_state_with_invalid_location(hass):
    """Test closest function state with invalid location."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {"latitude": "invalid latitude", "longitude": hass.config.longitude + 0.1},
    )

    assert (
        template.Template(
            "{{ closest(states.test_domain.closest_home, states) }}", hass
        ).async_render()
        is None
    )


def test_closest_function_invalid_coordinates(hass):
    """Test closest function invalid coordinates."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    assert (
        template.Template(
            '{{ closest("invalid", "coord", states) }}', hass
        ).async_render()
        is None
    )
    assert (
        template.Template(
            '{{ states | closest("invalid", "coord") }}', hass
        ).async_render()
        is None
    )


def test_closest_function_no_location_states(hass):
    """Test closest function without location states."""
    assert (
        template.Template("{{ closest(states).entity_id }}", hass).async_render() == ""
    )


def test_generate_filter_iterators(hass):
    """Test extract entities function with none entities stuff."""
    info = render_to_info(
        hass,
        """
        {% for state in states %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "", all_states=True)

    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "", domains=["sensor"])

    hass.states.async_set("sensor.test_sensor", "off", {"attr": "value"})

    # Don't need the entity because the state is not accessed
    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor", domains=["sensor"])

    # But we do here because the state gets accessed
    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}={{ state.state }},
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor=off,", [], ["sensor"])

    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}={{ state.attributes.attr }},
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor=value,", [], ["sensor"])


def test_generate_select(hass):
    """Test extract entities function with none entities stuff."""
    template_str = """
{{ states.sensor|selectattr("state","equalto","off")
|join(",", attribute="entity_id") }}
        """

    tmp = template.Template(template_str, hass)
    info = tmp.async_render_to_info()
    assert_result_info(info, "", [], [])
    assert info.domains_lifecycle == {"sensor"}

    hass.states.async_set("sensor.test_sensor", "off", {"attr": "value"})
    hass.states.async_set("sensor.test_sensor_on", "on")

    info = tmp.async_render_to_info()
    assert_result_info(
        info,
        "sensor.test_sensor",
        [],
        ["sensor"],
    )
    assert info.domains_lifecycle == {"sensor"}


async def test_async_render_to_info_in_conditional(hass):
    """Test extract entities function with none entities stuff."""
    template_str = """
{{ states("sensor.xyz") == "dog" }}
        """

    tmp = template.Template(template_str, hass)
    info = tmp.async_render_to_info()
    assert_result_info(info, False, ["sensor.xyz"], [])

    hass.states.async_set("sensor.xyz", "dog")
    hass.states.async_set("sensor.cow", "True")
    await hass.async_block_till_done()

    template_str = """
{% if states("sensor.xyz") == "dog" %}
  {{ states("sensor.cow") }}
{% else %}
  {{ states("sensor.pig") }}
{% endif %}
        """

    tmp = template.Template(template_str, hass)
    info = tmp.async_render_to_info()
    assert_result_info(info, True, ["sensor.xyz", "sensor.cow"], [])

    hass.states.async_set("sensor.xyz", "sheep")
    hass.states.async_set("sensor.pig", "oink")

    await hass.async_block_till_done()

    tmp = template.Template(template_str, hass)
    info = tmp.async_render_to_info()
    assert_result_info(info, "oink", ["sensor.xyz", "sensor.pig"], [])


def test_jinja_namespace(hass):
    """Test Jinja's namespace command can be used."""
    test_template = template.Template(
        (
            "{% set ns = namespace(a_key='') %}"
            "{% set ns.a_key = states.sensor.dummy.state %}"
            "{{ ns.a_key }}"
        ),
        hass,
    )

    hass.states.async_set("sensor.dummy", "a value")
    assert test_template.async_render() == "a value"

    hass.states.async_set("sensor.dummy", "another value")
    assert test_template.async_render() == "another value"


def test_state_with_unit(hass):
    """Test the state_with_unit property helper."""
    hass.states.async_set("sensor.test", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "wow")

    tpl = template.Template("{{ states.sensor.test.state_with_unit }}", hass)

    assert tpl.async_render() == "23 beers"

    tpl = template.Template("{{ states.sensor.test2.state_with_unit }}", hass)

    assert tpl.async_render() == "wow"

    tpl = template.Template(
        "{% for state in states %}{{ state.state_with_unit }} {% endfor %}", hass
    )

    assert tpl.async_render() == "23 beers wow"

    tpl = template.Template("{{ states.sensor.non_existing.state_with_unit }}", hass)

    assert tpl.async_render() == ""


def test_length_of_states(hass):
    """Test fetching the length of states."""
    hass.states.async_set("sensor.test", "23")
    hass.states.async_set("sensor.test2", "wow")
    hass.states.async_set("climate.test2", "cooling")

    tpl = template.Template("{{ states | length }}", hass)
    assert tpl.async_render() == 3

    tpl = template.Template("{{ states.sensor | length }}", hass)
    assert tpl.async_render() == 2


def test_render_complex_handling_non_template_values(hass):
    """Test that we can render non-template fields."""
    assert template.render_complex(
        {True: 1, False: template.Template("{{ hello }}", hass)}, {"hello": 2}
    ) == {True: 1, False: 2}


def test_urlencode(hass):
    """Test the urlencode method."""
    tpl = template.Template(
        ("{% set dict = {'foo': 'x&y', 'bar': 42} %}" "{{ dict | urlencode }}"),
        hass,
    )
    assert tpl.async_render() == "foo=x%26y&bar=42"
    tpl = template.Template(
        ("{% set string = 'the quick brown fox = true' %}" "{{ string | urlencode }}"),
        hass,
    )
    assert tpl.async_render() == "the%20quick%20brown%20fox%20%3D%20true"


async def test_cache_garbage_collection():
    """Test caching a template."""
    template_string = (
        "{% set dict = {'foo': 'x&y', 'bar': 42} %} {{ dict | urlencode }}"
    )
    tpl = template.Template(
        (template_string),
    )
    tpl.ensure_valid()
    assert template._NO_HASS_ENV.template_cache.get(
        template_string
    )  # pylint: disable=protected-access

    tpl2 = template.Template(
        (template_string),
    )
    tpl2.ensure_valid()
    assert template._NO_HASS_ENV.template_cache.get(
        template_string
    )  # pylint: disable=protected-access

    del tpl
    assert template._NO_HASS_ENV.template_cache.get(
        template_string
    )  # pylint: disable=protected-access
    del tpl2
    assert not template._NO_HASS_ENV.template_cache.get(
        template_string
    )  # pylint: disable=protected-access


def test_is_template_string():
    """Test is template string."""
    assert template.is_template_string("{{ x }}") is True
    assert template.is_template_string("{% if x == 2 %}1{% else %}0{%end if %}") is True
    assert template.is_template_string("{# a comment #} Hey") is True
    assert template.is_template_string("1") is False
    assert template.is_template_string("Some Text") is False


async def test_protected_blocked(hass):
    """Test accessing __getattr__ produces a template error."""
    tmp = template.Template('{{ states.__getattr__("any") }}', hass)
    with pytest.raises(TemplateError):
        tmp.async_render()

    tmp = template.Template('{{ states.sensor.__getattr__("any") }}', hass)
    with pytest.raises(TemplateError):
        tmp.async_render()

    tmp = template.Template('{{ states.sensor.any.__getattr__("any") }}', hass)
    with pytest.raises(TemplateError):
        tmp.async_render()


async def test_demo_template(hass):
    """Test the demo template works as expected."""
    hass.states.async_set("sun.sun", "above", {"elevation": 50, "next_rising": "later"})
    for i in range(2):
        hass.states.async_set(f"sensor.sensor{i}", "on")

    demo_template_str = """
{## Imitate available variables: ##}
{% set my_test_json = {
  "temperature": 25,
  "unit": "°C"
} %}

The temperature is {{ my_test_json.temperature }} {{ my_test_json.unit }}.

{% if is_state("sun.sun", "above_horizon") -%}
  The sun rose {{ relative_time(states.sun.sun.last_changed) }} ago.
{%- else -%}
  The sun will rise at {{ as_timestamp(strptime(state_attr("sun.sun", "next_rising"), "")) | timestamp_local }}.
{%- endif %}

For loop example getting 3 entity values:

{% for states in states | slice(3) -%}
  {% set state = states | first %}
  {%- if loop.first %}The {% elif loop.last %} and the {% else %}, the {% endif -%}
  {{ state.name | lower }} is {{state.state_with_unit}}
{%- endfor %}.
"""
    tmp = template.Template(demo_template_str, hass)

    result = tmp.async_render()
    assert "The temperature is 25" in result
    assert "is on" in result
    assert "sensor0" in result
    assert "sensor1" in result
    assert "sun" in result


async def test_slice_states(hass):
    """Test iterating states with a slice."""
    hass.states.async_set("sensor.test", "23")

    tpl = template.Template(
        "{% for states in states | slice(1) -%}{% set state = states | first %}{{ state.entity_id }}{%- endfor %}",
        hass,
    )
    assert tpl.async_render() == "sensor.test"


async def test_lifecycle(hass):
    """Test that we limit template render info for lifecycle events."""
    hass.states.async_set("sun.sun", "above", {"elevation": 50, "next_rising": "later"})
    for i in range(2):
        hass.states.async_set(f"sensor.sensor{i}", "on")
    hass.states.async_set("sensor.removed", "off")

    await hass.async_block_till_done()

    hass.states.async_set("sun.sun", "below", {"elevation": 60, "next_rising": "later"})
    for i in range(2):
        hass.states.async_set(f"sensor.sensor{i}", "off")

    hass.states.async_set("sensor.new", "off")
    hass.states.async_remove("sensor.removed")

    await hass.async_block_till_done()

    tmp = template.Template("{{ states | count }}", hass)

    info = tmp.async_render_to_info()
    assert info.all_states is False
    assert info.all_states_lifecycle is True
    assert info.rate_limit is None
    assert info.has_time is False

    assert info.entities == set()
    assert info.domains == set()
    assert info.domains_lifecycle == set()

    assert info.filter("sun.sun") is False
    assert info.filter("sensor.sensor1") is False
    assert info.filter_lifecycle("sensor.new") is True
    assert info.filter_lifecycle("sensor.removed") is True


async def test_template_timeout(hass):
    """Test to see if a template will timeout."""
    for i in range(2):
        hass.states.async_set(f"sensor.sensor{i}", "on")

    tmp = template.Template("{{ states | count }}", hass)
    assert await tmp.async_render_will_timeout(3) is False

    tmp3 = template.Template("static", hass)
    assert await tmp3.async_render_will_timeout(3) is False

    tmp4 = template.Template("{{ var1 }}", hass)
    assert await tmp4.async_render_will_timeout(3, {"var1": "ok"}) is False

    slow_template_str = """
{% for var in range(1000) -%}
  {% for var in range(1000) -%}
    {{ var }}
  {%- endfor %}
{%- endfor %}
"""
    tmp5 = template.Template(slow_template_str, hass)
    assert await tmp5.async_render_will_timeout(0.000001) is True


async def test_template_timeout_raise(hass):
    """Test we can raise from."""
    tmp2 = template.Template("{{ error_invalid + 1 }}", hass)
    with pytest.raises(TemplateError):
        assert await tmp2.async_render_will_timeout(3) is False


async def test_lights(hass):
    """Test we can sort lights."""

    tmpl = """
          {% set lights_on = states.light|selectattr('state','eq','on')|map(attribute='name')|list %}
          {% if lights_on|length == 0 %}
            No lights on. Sleep well..
          {% elif lights_on|length == 1 %}
            The {{lights_on[0]}} light is on.
          {% elif lights_on|length == 2 %}
            The {{lights_on[0]}} and {{lights_on[1]}} lights are on.
          {% else %}
            The {{lights_on[:-1]|join(', ')}}, and {{lights_on[-1]}} lights are on.
          {% endif %}
    """
    states = []
    for i in range(10):
        states.append(f"light.sensor{i}")
        hass.states.async_set(f"light.sensor{i}", "on")

    tmp = template.Template(tmpl, hass)
    info = tmp.async_render_to_info()
    assert info.entities == set()
    assert info.domains == {"light"}

    assert "lights are on" in info.result()
    for i in range(10):
        assert f"sensor{i}" in info.result()


async def test_template_errors(hass):
    """Test template rendering wraps exceptions with TemplateError."""

    with pytest.raises(TemplateError):
        template.Template("{{ now() | rando }}", hass).async_render()

    with pytest.raises(TemplateError):
        template.Template("{{ utcnow() | rando }}", hass).async_render()

    with pytest.raises(TemplateError):
        template.Template("{{ now() | random }}", hass).async_render()

    with pytest.raises(TemplateError):
        template.Template("{{ utcnow() | random }}", hass).async_render()


async def test_state_attributes(hass):
    """Test state attributes."""
    hass.states.async_set("sensor.test", "23")

    tpl = template.Template(
        "{{ states.sensor.test.last_changed }}",
        hass,
    )
    assert tpl.async_render() == str(hass.states.get("sensor.test").last_changed)

    tpl = template.Template(
        "{{ states.sensor.test.object_id }}",
        hass,
    )
    assert tpl.async_render() == hass.states.get("sensor.test").object_id

    tpl = template.Template(
        "{{ states.sensor.test.domain }}",
        hass,
    )
    assert tpl.async_render() == hass.states.get("sensor.test").domain

    tpl = template.Template(
        "{{ states.sensor.test.context.id }}",
        hass,
    )
    assert tpl.async_render() == hass.states.get("sensor.test").context.id

    tpl = template.Template(
        "{{ states.sensor.test.state_with_unit }}",
        hass,
    )
    assert tpl.async_render() == 23

    tpl = template.Template(
        "{{ states.sensor.test.invalid_prop }}",
        hass,
    )
    assert tpl.async_render() == ""

    tpl = template.Template(
        "{{ states.sensor.test.invalid_prop.xx }}",
        hass,
    )
    with pytest.raises(TemplateError):
        tpl.async_render()


async def test_unavailable_states(hass):
    """Test watching unavailable states."""

    for i in range(10):
        hass.states.async_set(f"light.sensor{i}", "on")

    hass.states.async_set("light.unavailable", "unavailable")
    hass.states.async_set("light.unknown", "unknown")
    hass.states.async_set("light.none", "none")

    tpl = template.Template(
        "{{ states | selectattr('state', 'in', ['unavailable','unknown','none']) | map(attribute='entity_id') | list | join(', ') }}",
        hass,
    )
    assert tpl.async_render() == "light.none, light.unavailable, light.unknown"

    tpl = template.Template(
        "{{ states.light | selectattr('state', 'in', ['unavailable','unknown','none']) | map(attribute='entity_id') | list | join(', ') }}",
        hass,
    )
    assert tpl.async_render() == "light.none, light.unavailable, light.unknown"


async def test_legacy_templates(hass):
    """Test if old template behavior works when legacy templates are enabled."""
    hass.states.async_set("sensor.temperature", "12")

    assert (
        template.Template("{{ states.sensor.temperature.state }}", hass).async_render()
        == 12
    )

    await async_process_ha_core_config(hass, {"legacy_templates": True})
    assert (
        template.Template("{{ states.sensor.temperature.state }}", hass).async_render()
        == "12"
    )


async def test_no_result_parsing(hass):
    """Test if templates results are not parsed."""
    hass.states.async_set("sensor.temperature", "12")

    assert (
        template.Template("{{ states.sensor.temperature.state }}", hass).async_render(
            parse_result=False
        )
        == "12"
    )

    assert (
        template.Template("{{ false }}", hass).async_render(parse_result=False)
        == "False"
    )

    assert (
        template.Template("{{ [1, 2, 3] }}", hass).async_render(parse_result=False)
        == "[1, 2, 3]"
    )


async def test_is_static_still_ast_evals(hass):
    """Test is_static still convers to native type."""
    tpl = template.Template("[1, 2]", hass)
    assert tpl.is_static
    assert tpl.async_render() == [1, 2]


async def test_result_wrappers(hass):
    """Test result wrappers."""
    for text, native, orig_type, schema in (
        ("[1, 2]", [1, 2], list, vol.Schema([int])),
        ("{1, 2}", {1, 2}, set, vol.Schema({int})),
        ("(1, 2)", (1, 2), tuple, vol.ExactSequence([int, int])),
        ('{"hello": True}', {"hello": True}, dict, vol.Schema({"hello": bool})),
    ):
        tpl = template.Template(text, hass)
        result = tpl.async_render()
        assert isinstance(result, orig_type)
        assert isinstance(result, template.ResultWrapper)
        assert result == native
        assert result.render_result == text
        schema(result)  # should not raise
        # Result with render text stringifies to original text
        assert str(result) == text
        # Result without render text stringifies same as original type
        assert str(template.RESULT_WRAPPERS[orig_type](native)) == str(
            orig_type(native)
        )


async def test_parse_result(hass):
    """Test parse result."""
    for tpl, result in (
        ('{{ "{{}}" }}', "{{}}"),
        ("not-something", "not-something"),
        ("2a", "2a"),
        ("123E5", "123E5"),
        ("1j", "1j"),
        ("1e+100", "1e+100"),
        ("0xface", "0xface"),
        ("123", 123),
        ("10", 10),
        ("123.0", 123.0),
        (".5", 0.5),
        ("0.5", 0.5),
        ("-1", -1),
        ("-1.0", -1.0),
        ("+1", 1),
        ("5.", 5.0),
        ("123_123_123", "123_123_123"),
        # ("+48100200300", "+48100200300"),  # phone number
        ("010", "010"),
        ("0011101.00100001010001", "0011101.00100001010001"),
    ):
        assert template.Template(tpl, hass).async_render() == result


async def test_undefined_variable(hass, caplog):
    """Test a warning is logged on undefined variables."""
    tpl = template.Template("{{ no_such_variable }}", hass)
    assert tpl.async_render() == ""
    assert (
        "Template variable warning: 'no_such_variable' is undefined when rendering '{{ no_such_variable }}'"
        in caplog.text
    )

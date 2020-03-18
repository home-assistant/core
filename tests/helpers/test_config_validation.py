"""Test config validators."""
from datetime import date, datetime, timedelta
import enum
import os
from socket import _GLOBAL_DEFAULT_TIMEOUT
from unittest.mock import Mock, patch
import uuid

import pytest
import voluptuous as vol

import homeassistant
import homeassistant.helpers.config_validation as cv


def test_boolean():
    """Test boolean validation."""
    schema = vol.Schema(cv.boolean)

    for value in (
        None,
        "T",
        "negative",
        "lock",
        "tr  ue",
        [],
        [1, 2],
        {"one": "two"},
        test_boolean,
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("true", "On", "1", "YES", "   true  ", "enable", 1, 50, True, 0.1):
        assert schema(value)

    for value in ("false", "Off", "0", "NO", "disable", 0, False):
        assert not schema(value)


def test_latitude():
    """Test latitude validation."""
    schema = vol.Schema(cv.latitude)

    for value in ("invalid", None, -91, 91, "-91", "91", "123.01A"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("-89", 89, "12.34"):
        schema(value)


def test_longitude():
    """Test longitude validation."""
    schema = vol.Schema(cv.longitude)

    for value in ("invalid", None, -181, 181, "-181", "181", "123.01A"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("-179", 179, "12.34"):
        schema(value)


def test_port():
    """Test TCP/UDP network port."""
    schema = vol.Schema(cv.port)

    for value in ("invalid", None, -1, 0, 80000, "81000"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ("1000", 21, 24574):
        schema(value)


def test_isfile():
    """Validate that the value is an existing file."""
    schema = vol.Schema(cv.isfile)

    fake_file = "this-file-does-not.exist"
    assert not os.path.isfile(fake_file)

    for value in ("invalid", None, -1, 0, 80000, fake_file):
        with pytest.raises(vol.Invalid):
            schema(value)

    # patching methods that allow us to fake a file existing
    # with write access
    with patch("os.path.isfile", Mock(return_value=True)), patch(
        "os.access", Mock(return_value=True)
    ):
        schema("test.txt")


def test_url():
    """Test URL."""
    schema = vol.Schema(cv.url)

    for value in (
        "invalid",
        None,
        100,
        "htp://ha.io",
        "http//ha.io",
        "http://??,**",
        "https://??,**",
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        "http://localhost",
        "https://localhost/test/index.html",
        "http://home-assistant.io",
        "http://home-assistant.io/test/",
        "https://community.home-assistant.io/",
    ):
        assert schema(value)


def test_platform_config():
    """Test platform config validation."""
    options = ({}, {"hello": "world"})
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.PLATFORM_SCHEMA(value)

    options = ({"platform": "mqtt"}, {"platform": "mqtt", "beer": "yes"})
    for value in options:
        cv.PLATFORM_SCHEMA_BASE(value)


def test_ensure_list():
    """Test ensure_list."""
    schema = vol.Schema(cv.ensure_list)
    assert [] == schema(None)
    assert [1] == schema(1)
    assert [1] == schema([1])
    assert ["1"] == schema("1")
    assert ["1"] == schema(["1"])
    assert [{"1": "2"}] == schema({"1": "2"})


def test_entity_id():
    """Test entity ID validation."""
    schema = vol.Schema(cv.entity_id)

    with pytest.raises(vol.MultipleInvalid):
        schema("invalid_entity")

    assert schema("sensor.LIGHT") == "sensor.light"


def test_entity_ids():
    """Test entity ID validation."""
    schema = vol.Schema(cv.entity_ids)

    options = (
        "invalid_entity",
        "sensor.light,sensor_invalid",
        ["invalid_entity"],
        ["sensor.light", "sensor_invalid"],
        ["sensor.light,sensor_invalid"],
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = ([], ["sensor.light"], "sensor.light")
    for value in options:
        schema(value)

    assert schema("sensor.LIGHT, light.kitchen ") == ["sensor.light", "light.kitchen"]


def test_entity_domain():
    """Test entity domain validation."""
    schema = vol.Schema(cv.entity_domain("sensor"))

    options = ("invalid_entity", "cover.demo")

    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            print(value)
            schema(value)

    assert schema("sensor.LIGHT") == "sensor.light"


def test_entities_domain():
    """Test entities domain validation."""
    schema = vol.Schema(cv.entities_domain("sensor"))

    options = (
        None,
        "",
        "invalid_entity",
        ["sensor.light", "cover.demo"],
        ["sensor.light", "sensor_invalid"],
    )

    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = ("sensor.light", ["SENSOR.light"], ["sensor.light", "sensor.demo"])
    for value in options:
        schema(value)

    assert schema("sensor.LIGHT, sensor.demo ") == ["sensor.light", "sensor.demo"]
    assert schema(["sensor.light", "SENSOR.demo"]) == ["sensor.light", "sensor.demo"]


def test_ensure_list_csv():
    """Test ensure_list_csv."""
    schema = vol.Schema(cv.ensure_list_csv)

    options = (None, 12, [], ["string"], "string1,string2")
    for value in options:
        schema(value)

    assert schema("string1, string2 ") == ["string1", "string2"]


def test_event_schema():
    """Test event_schema validation."""
    options = (
        {},
        None,
        {"event_data": {}},
        {"event": "state_changed", "event_data": 1},
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.EVENT_SCHEMA(value)

    options = (
        {"event": "state_changed"},
        {"event": "state_changed", "event_data": {"hello": "world"}},
    )
    for value in options:
        cv.EVENT_SCHEMA(value)


def test_icon():
    """Test icon validation."""
    schema = vol.Schema(cv.icon)

    for value in (False, "work"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema("mdi:work")
    schema("custom:prefix")


def test_time_period():
    """Test time_period validation."""
    schema = vol.Schema(cv.time_period)

    options = (None, "", "hello:world", "12:", "12:34:56:78", {}, {"wrong_key": -10})
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = ("8:20", "23:59", "-8:20", "-23:59:59", "-48:00", {"minutes": 5}, 1, "5")
    for value in options:
        schema(value)

    assert timedelta(seconds=180) == schema("180")
    assert timedelta(hours=23, minutes=59) == schema("23:59")
    assert -1 * timedelta(hours=1, minutes=15) == schema("-1:15")


def test_remove_falsy():
    """Test remove falsy."""
    assert cv.remove_falsy([0, None, 1, "1", {}, [], ""]) == [1, "1"]


def test_service():
    """Test service validation."""
    schema = vol.Schema(cv.service)

    with pytest.raises(vol.MultipleInvalid):
        schema("invalid_turn_on")

    schema("homeassistant.turn_on")


def test_service_schema():
    """Test service_schema validation."""
    options = (
        {},
        None,
        {
            "service": "homeassistant.turn_on",
            "service_template": "homeassistant.turn_on",
        },
        {"data": {"entity_id": "light.kitchen"}},
        {"service": "homeassistant.turn_on", "data": None},
        {
            "service": "homeassistant.turn_on",
            "data_template": {"brightness": "{{ no_end"},
        },
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.SERVICE_SCHEMA(value)

    options = (
        {"service": "homeassistant.turn_on"},
        {"service": "homeassistant.turn_on", "entity_id": "light.kitchen"},
        {"service": "light.turn_on", "entity_id": "all"},
        {
            "service": "homeassistant.turn_on",
            "entity_id": ["light.kitchen", "light.ceiling"],
        },
    )
    for value in options:
        cv.SERVICE_SCHEMA(value)


def test_slug():
    """Test slug validation."""
    schema = vol.Schema(cv.slug)

    for value in (None, "hello world"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (12345, "hello"):
        schema(value)


def test_string():
    """Test string validation."""
    schema = vol.Schema(cv.string)

    with pytest.raises(vol.Invalid):
        schema(None)

    with pytest.raises(vol.Invalid):
        schema([])

    with pytest.raises(vol.Invalid):
        schema({})

    for value in (True, 1, "hello"):
        schema(value)


def test_temperature_unit():
    """Test temperature unit validation."""
    schema = vol.Schema(cv.temperature_unit)

    with pytest.raises(vol.MultipleInvalid):
        schema("K")

    schema("C")
    schema("F")


def test_x10_address():
    """Test x10 addr validator."""
    schema = vol.Schema(cv.x10_address)
    with pytest.raises(vol.Invalid):
        schema("Q1")
        schema("q55")
        schema("garbage_addr")

    schema("a1")
    schema("C11")


def test_template():
    """Test template validator."""
    schema = vol.Schema(cv.template)

    for value in (None, "{{ partial_print }", "{% if True %}Hello", ["test"]):
        with pytest.raises(vol.Invalid):
            schema(value)

    options = (
        1,
        "Hello",
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
    )
    for value in options:
        schema(value)


def test_template_complex():
    """Test template_complex validator."""
    schema = vol.Schema(cv.template_complex)

    for value in ("{{ partial_print }", "{% if True %}Hello"):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        1,
        "Hello",
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
        {"test": 1, "test2": "{{ beer }}"},
        ["{{ beer }}", 1],
    )
    for value in options:
        schema(value)

    # ensure the validator didn't mutate the input
    assert options == (
        1,
        "Hello",
        "{{ beer }}",
        "{% if 1 == 1 %}Hello{% else %}World{% endif %}",
        {"test": 1, "test2": "{{ beer }}"},
        ["{{ beer }}", 1],
    )

    # Ensure we don't mutate non-string types that cannot be templates.
    for value in (1, True, None):
        assert schema(value) == value


def test_time_zone():
    """Test time zone validation."""
    schema = vol.Schema(cv.time_zone)

    with pytest.raises(vol.MultipleInvalid):
        schema("America/Do_Not_Exist")

    schema("America/Los_Angeles")
    schema("UTC")


def test_date():
    """Test date validation."""
    schema = vol.Schema(cv.date)

    for value in ["Not a date", "23:42", "2016-11-23T18:59:08"]:
        with pytest.raises(vol.Invalid):
            schema(value)

    schema(datetime.now().date())
    schema("2016-11-23")


def test_time():
    """Test date validation."""
    schema = vol.Schema(cv.time)

    for value in ["Not a time", "2016-11-23", "2016-11-23T18:59:08"]:
        with pytest.raises(vol.Invalid):
            schema(value)

    schema(datetime.now().time())
    schema("23:42:00")
    schema("23:42")


def test_datetime():
    """Test date time validation."""
    schema = vol.Schema(cv.datetime)
    for value in [date.today(), "Wrong DateTime"]:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema(datetime.now())
    schema("2016-11-23T18:59:08")


def test_multi_select():
    """Test multi select validation.

    Expected behavior:
        - Will not accept any input but a list
        - Will not accept selections outside of configured scope
    """
    schema = vol.Schema(cv.multi_select({"paulus": "Paulus", "robban": "Robban"}))

    with pytest.raises(vol.Invalid):
        schema("robban")
        schema(["paulus", "martinhj"])

    schema(["robban", "paulus"])


def test_multi_select_in_serializer():
    """Test multi_select with custom_serializer."""
    assert cv.custom_serializer(cv.multi_select({"paulus": "Paulus"})) == {
        "type": "multi_select",
        "options": {"paulus": "Paulus"},
    }


@pytest.fixture
def schema():
    """Create a schema used for testing deprecation."""
    return vol.Schema({"venus": cv.boolean, "mars": cv.boolean, "jupiter": cv.boolean})


@pytest.fixture
def version(monkeypatch):
    """Patch the version used for testing to 0.5.0."""
    monkeypatch.setattr(homeassistant.const, "__version__", "0.5.0")


def test_deprecated_with_no_optionals(caplog, schema):
    """
    Test deprecation behaves correctly when optional params are None.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema without changing any values
        - No warning or difference in output if key is not provided
    """
    deprecated_schema = vol.All(cv.deprecated("mars"), schema)

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert caplog.records[0].name in [
        __name__,
        "homeassistant.helpers.config_validation",
    ]
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please remove it from your configuration"
    ) in caplog.text
    assert test_data == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_replacement_key(caplog, schema):
    """
    Test deprecation behaves correctly when only a replacement key is provided.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning or difference in output if neither key nor
            replacement_key are provided
    """
    deprecated_schema = vol.All(
        cv.deprecated("mars", replacement_key="jupiter"), schema
    )

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please replace it with 'jupiter'"
    ) in caplog.text
    assert {"jupiter": True} == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"jupiter": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_invalidation_version(caplog, schema, version):
    """
    Test deprecation behaves correctly with only an invalidation_version.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema without changing any values
        - No warning or difference in output if key is not provided
        - Once the invalidation_version is crossed, raises vol.Invalid if key
            is detected
    """
    deprecated_schema = vol.All(
        cv.deprecated("mars", invalidation_version="1.0.0"), schema
    )

    message = (
        "The 'mars' option (with value 'True') is deprecated, "
        "please remove it from your configuration. "
        "This option will become invalid in version 1.0.0"
    )

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert message in caplog.text
    assert test_data == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"venus": False}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    invalidated_schema = vol.All(
        cv.deprecated("mars", invalidation_version="0.1.0"), schema
    )
    test_data = {"mars": True}
    with pytest.raises(vol.MultipleInvalid) as exc_info:
        invalidated_schema(test_data)
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please remove it from your configuration. This option will "
        "become invalid in version 0.1.0"
    ) == str(exc_info.value)


def test_deprecated_with_replacement_key_and_invalidation_version(
    caplog, schema, version
):
    """
    Test deprecation behaves with a replacement key & invalidation_version.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning or difference in output if neither key nor
            replacement_key are provided
        - Once the invalidation_version is crossed, raises vol.Invalid if key
        is detected
    """
    deprecated_schema = vol.All(
        cv.deprecated("mars", replacement_key="jupiter", invalidation_version="1.0.0"),
        schema,
    )

    warning = (
        "The 'mars' option (with value 'True') is deprecated, "
        "please replace it with 'jupiter'. This option will become "
        "invalid in version 1.0.0"
    )

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert warning in caplog.text
    assert {"jupiter": True} == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"jupiter": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    invalidated_schema = vol.All(
        cv.deprecated("mars", replacement_key="jupiter", invalidation_version="0.1.0"),
        schema,
    )
    test_data = {"mars": True}
    with pytest.raises(vol.MultipleInvalid) as exc_info:
        invalidated_schema(test_data)
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please replace it with 'jupiter'. This option will become "
        "invalid in version 0.1.0"
    ) == str(exc_info.value)


def test_deprecated_with_default(caplog, schema):
    """
    Test deprecation behaves correctly with a default value.

    This is likely a scenario that would never occur.

    Expected behavior:
        - Behaves identically as when the default value was not present
    """
    deprecated_schema = vol.All(cv.deprecated("mars", default=False), schema)

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert caplog.records[0].name == __name__
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please remove it from your configuration"
    ) in caplog.text
    assert test_data == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_replacement_key_and_default(caplog, schema):
    """
    Test deprecation with a replacement key and default.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning if neither key nor replacement_key are provided
            - Adds replacement_key with default value in this case
    """
    deprecated_schema = vol.All(
        cv.deprecated("mars", replacement_key="jupiter", default=False), schema
    )

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please replace it with 'jupiter'"
    ) in caplog.text
    assert {"jupiter": True} == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"jupiter": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert {"venus": True, "jupiter": False} == output

    deprecated_schema_with_default = vol.All(
        vol.Schema(
            {
                "venus": cv.boolean,
                vol.Optional("mars", default=False): cv.boolean,
                vol.Optional("jupiter", default=False): cv.boolean,
            }
        ),
        cv.deprecated("mars", replacement_key="jupiter", default=False),
    )

    test_data = {"mars": True}
    output = deprecated_schema_with_default(test_data.copy())
    assert len(caplog.records) == 1
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please replace it with 'jupiter'"
    ) in caplog.text
    assert {"jupiter": True} == output


def test_deprecated_with_replacement_key_invalidation_version_default(
    caplog, schema, version
):
    """
    Test deprecation with a replacement key, invalidation_version & default.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning if neither key nor replacement_key are provided
            - Adds replacement_key with default value in this case
        - Once the invalidation_version is crossed, raises vol.Invalid if key
        is detected
    """
    deprecated_schema = vol.All(
        cv.deprecated(
            "mars",
            replacement_key="jupiter",
            invalidation_version="1.0.0",
            default=False,
        ),
        schema,
    )

    test_data = {"mars": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please replace it with 'jupiter'. This option will become "
        "invalid in version 1.0.0"
    ) in caplog.text
    assert {"jupiter": True} == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {"jupiter": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {"venus": True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert {"venus": True, "jupiter": False} == output

    invalidated_schema = vol.All(
        cv.deprecated("mars", replacement_key="jupiter", invalidation_version="0.1.0"),
        schema,
    )
    test_data = {"mars": True}
    with pytest.raises(vol.MultipleInvalid) as exc_info:
        invalidated_schema(test_data)
    assert (
        "The 'mars' option (with value 'True') is deprecated, "
        "please replace it with 'jupiter'. This option will become "
        "invalid in version 0.1.0"
    ) == str(exc_info.value)


def test_deprecated_cant_find_module():
    """Test if the current module cannot be inspected."""
    with patch("inspect.getmodule", return_value=None):
        # This used to raise.
        cv.deprecated(
            "mars",
            replacement_key="jupiter",
            invalidation_version="1.0.0",
            default=False,
        )


def test_key_dependency():
    """Test key_dependency validator."""
    schema = vol.Schema(cv.key_dependency("beer", "soda"))

    options = {"beer": None}
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = ({"beer": None, "soda": None}, {"soda": None}, {})
    for value in options:
        schema(value)


def test_has_at_most_one_key():
    """Test has_at_most_one_key validator."""
    schema = vol.Schema(cv.has_at_most_one_key("beer", "soda"))

    for value in (None, [], {"beer": None, "soda": None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({}, {"beer": None}, {"soda": None}):
        schema(value)


def test_has_at_least_one_key():
    """Test has_at_least_one_key validator."""
    schema = vol.Schema(cv.has_at_least_one_key("beer", "soda"))

    for value in (None, [], {}, {"wine": None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({"beer": None}, {"soda": None}):
        schema(value)


def test_enum():
    """Test enum validator."""

    class TestEnum(enum.Enum):
        """Test enum."""

        value1 = "Value 1"
        value2 = "Value 2"

    schema = vol.Schema(cv.enum(TestEnum))

    with pytest.raises(vol.Invalid):
        schema("value3")


def test_socket_timeout():  # pylint: disable=invalid-name
    """Test socket timeout validator."""
    schema = vol.Schema(cv.socket_timeout)

    with pytest.raises(vol.Invalid):
        schema(0.0)

    with pytest.raises(vol.Invalid):
        schema(-1)

    assert _GLOBAL_DEFAULT_TIMEOUT == schema(None)

    assert schema(1) == 1.0


def test_matches_regex():
    """Test matches_regex validator."""
    schema = vol.Schema(cv.matches_regex(".*uiae.*"))

    with pytest.raises(vol.Invalid):
        schema(1.0)

    with pytest.raises(vol.Invalid):
        schema("  nrtd   ")

    test_str = "This is a test including uiae."
    assert schema(test_str) == test_str


def test_is_regex():
    """Test the is_regex validator."""
    schema = vol.Schema(cv.is_regex)

    with pytest.raises(vol.Invalid):
        schema("(")

    with pytest.raises(vol.Invalid):
        schema({"a dict": "is not a regex"})

    valid_re = ".*"
    schema(valid_re)


def test_comp_entity_ids():
    """Test config validation for component entity IDs."""
    schema = vol.Schema(cv.comp_entity_ids)

    for valid in (
        "ALL",
        "all",
        "AlL",
        "light.kitchen",
        ["light.kitchen"],
        ["light.kitchen", "light.ceiling"],
        [],
    ):
        schema(valid)

    for invalid in (["light.kitchen", "not-entity-id"], "*", ""):
        with pytest.raises(vol.Invalid):
            schema(invalid)


def test_uuid4_hex(caplog):
    """Test uuid validation."""
    schema = vol.Schema(cv.uuid4_hex)

    for value in ["Not a hex string", "0", 0]:
        with pytest.raises(vol.Invalid):
            schema(value)

    with pytest.raises(vol.Invalid):
        # the 13th char should be 4
        schema("a03d31b22eee1acc9b90eec40be6ed23")

    with pytest.raises(vol.Invalid):
        # the 17th char should be 8-a
        schema("a03d31b22eee4acc7b90eec40be6ed23")

    _hex = uuid.uuid4().hex
    assert schema(_hex) == _hex
    assert schema(_hex.upper()) == _hex


def test_key_value_schemas():
    """Test key value schemas."""
    schema = vol.Schema(
        cv.key_value_schemas(
            "mode",
            {
                "number": vol.Schema({"mode": "number", "data": int}),
                "string": vol.Schema({"mode": "string", "data": str}),
            },
        )
    )

    with pytest.raises(vol.Invalid) as excinfo:
        schema(True)
        assert str(excinfo.value) == "Expected a dictionary"

    for mode in None, "invalid":
        with pytest.raises(vol.Invalid) as excinfo:
            schema({"mode": mode})
        assert (
            str(excinfo.value)
            == f"Unexpected value for mode: '{mode}'. Expected number, string"
        )

    with pytest.raises(vol.Invalid) as excinfo:
        schema({"mode": "number", "data": "string-value"})
    assert str(excinfo.value) == "expected int for dictionary value @ data['data']"

    with pytest.raises(vol.Invalid) as excinfo:
        schema({"mode": "string", "data": 1})
    assert str(excinfo.value) == "expected str for dictionary value @ data['data']"

    for mode, data in (("number", 1), ("string", "hello")):
        schema({"mode": mode, "data": data})


def test_script(caplog):
    """Test script validation is user friendly."""
    for data, msg in (
        ({"delay": "{{ invalid"}, "should be format 'HH:MM'"),
        ({"wait_template": "{{ invalid"}, "invalid template"),
        ({"condition": "invalid"}, "Unexpected value for condition: 'invalid'"),
        ({"event": None}, "string value is None for dictionary value @ data['event']"),
        (
            {"device_id": None},
            "string value is None for dictionary value @ data['device_id']",
        ),
        (
            {"scene": "light.kitchen"},
            "Entity ID 'light.kitchen' does not belong to domain 'scene'",
        ),
    ):
        with pytest.raises(vol.Invalid) as excinfo:
            cv.script_action(data)

        assert msg in str(excinfo.value)

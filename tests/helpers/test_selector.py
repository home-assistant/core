"""Test selectors."""
import pytest
import voluptuous as vol

from homeassistant.helpers import config_validation as cv, selector
from homeassistant.util import dt as dt_util

FAKE_UUID = "a266a680b608c32770e6c45bfe6b8411"


@pytest.mark.parametrize(
    "schema",
    (
        {"device": None},
        {"entity": None},
    ),
)
def test_valid_base_schema(schema):
    """Test base schema validation."""
    selector.validate_selector(schema)


@pytest.mark.parametrize(
    "schema",
    (
        None,
        "not_a_dict",
        {},
        {"non_existing": {}},
        # Two keys
        {"device": {}, "entity": {}},
    ),
)
def test_invalid_base_schema(schema):
    """Test base schema validation."""
    with pytest.raises(vol.Invalid):
        selector.validate_selector(schema)


def test_validate_selector():
    """Test return is the same as input."""
    schema = {"device": {"manufacturer": "mock-manuf", "model": "mock-model"}}
    assert schema == selector.validate_selector(schema)


def _test_selector(
    selector_type, schema, valid_selections, invalid_selections, converter=None
):
    """Help test a selector."""

    def default_converter(x):
        return x

    if converter is None:
        converter = default_converter

    # Validate selector configuration
    selector.validate_selector({selector_type: schema})

    # Use selector in schema and validate
    vol_schema = vol.Schema({"selection": selector.selector({selector_type: schema})})
    for selection in valid_selections:
        assert vol_schema({"selection": selection}) == {
            "selection": converter(selection)
        }
    for selection in invalid_selections:
        with pytest.raises(vol.Invalid):
            vol_schema({"selection": selection})

    # Serialize selector
    selector_instance = selector.selector({selector_type: schema})
    assert cv.custom_serializer(selector_instance) == {
        "selector": {selector_type: selector_instance.config}
    }


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (None, ("abc123",), (None,)),
        ({}, ("abc123",), (None,)),
        ({"integration": "zha"}, ("abc123",), (None,)),
        ({"manufacturer": "mock-manuf"}, ("abc123",), (None,)),
        ({"model": "mock-model"}, ("abc123",), (None,)),
        ({"manufacturer": "mock-manuf", "model": "mock-model"}, ("abc123",), (None,)),
        (
            {"integration": "zha", "manufacturer": "mock-manuf", "model": "mock-model"},
            ("abc123",),
            (None,),
        ),
        ({"entity": {"device_class": "motion"}}, ("abc123",), (None,)),
        (
            {
                "integration": "zha",
                "manufacturer": "mock-manuf",
                "model": "mock-model",
                "entity": {"domain": "binary_sensor", "device_class": "motion"},
            },
            ("abc123",),
            (None,),
        ),
    ),
)
def test_device_selector_schema(schema, valid_selections, invalid_selections):
    """Test device selector."""
    _test_selector("device", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        ({}, ("sensor.abc123", FAKE_UUID), (None, "abc123")),
        ({"integration": "zha"}, ("sensor.abc123", FAKE_UUID), (None, "abc123")),
        ({"domain": "light"}, ("light.abc123", FAKE_UUID), (None, "sensor.abc123")),
        ({"device_class": "motion"}, ("sensor.abc123", FAKE_UUID), (None, "abc123")),
        (
            {"integration": "zha", "domain": "light"},
            ("light.abc123", FAKE_UUID),
            (None, "sensor.abc123"),
        ),
        (
            {"integration": "zha", "domain": "binary_sensor", "device_class": "motion"},
            ("binary_sensor.abc123", FAKE_UUID),
            (None, "sensor.abc123"),
        ),
    ),
)
def test_entity_selector_schema(schema, valid_selections, invalid_selections):
    """Test entity selector."""
    _test_selector("entity", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        ({}, ("abc123",), (None,)),
        ({"entity": {}}, ("abc123",), (None,)),
        ({"entity": {"domain": "light"}}, ("abc123",), (None,)),
        (
            {"entity": {"domain": "binary_sensor", "device_class": "motion"}},
            ("abc123",),
            (None,),
        ),
        (
            {
                "entity": {
                    "domain": "binary_sensor",
                    "device_class": "motion",
                    "integration": "demo",
                }
            },
            ("abc123",),
            (None,),
        ),
        (
            {"device": {"integration": "demo", "model": "mock-model"}},
            ("abc123",),
            (None,),
        ),
        (
            {
                "entity": {"domain": "binary_sensor", "device_class": "motion"},
                "device": {"integration": "demo", "model": "mock-model"},
            },
            ("abc123",),
            (None,),
        ),
    ),
)
def test_area_selector_schema(schema, valid_selections, invalid_selections):
    """Test area selector."""
    _test_selector("area", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {"min": 10, "max": 50},
            (
                10,
                50,
            ),
            (9, 51),
        ),
        ({"min": -100, "max": 100, "step": 5}, (), ()),
        ({"min": -20, "max": -10, "mode": "box"}, (), ()),
        (
            {"min": 0, "max": 100, "unit_of_measurement": "seconds", "mode": "slider"},
            (),
            (),
        ),
        ({"min": 10, "max": 1000, "mode": "slider", "step": 0.5}, (), ()),
    ),
)
def test_number_selector_schema(schema, valid_selections, invalid_selections):
    """Test number selector."""
    _test_selector("number", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (({}, ("abc123",), (None,)),),
)
def test_addon_selector_schema(schema, valid_selections, invalid_selections):
    """Test add-on selector."""
    _test_selector("addon", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (({}, (1, "one", None), ()),),  # Everything can be coarced to bool
)
def test_boolean_selector_schema(schema, valid_selections, invalid_selections):
    """Test boolean selector."""
    _test_selector("boolean", schema, valid_selections, invalid_selections, bool)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (({}, ("00:00:00",), ("blah", None)),),
)
def test_time_selector_schema(schema, valid_selections, invalid_selections):
    """Test time selector."""
    _test_selector(
        "time", schema, valid_selections, invalid_selections, dt_util.parse_time
    )


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        ({}, ({"entity_id": ["sensor.abc123"]},), ("abc123", None)),
        ({"entity": {}}, (), ()),
        ({"entity": {"domain": "light"}}, (), ()),
        ({"entity": {"domain": "binary_sensor", "device_class": "motion"}}, (), ()),
        (
            {
                "entity": {
                    "domain": "binary_sensor",
                    "device_class": "motion",
                    "integration": "demo",
                }
            },
            (),
            (),
        ),
        ({"device": {"integration": "demo", "model": "mock-model"}}, (), ()),
        (
            {
                "entity": {"domain": "binary_sensor", "device_class": "motion"},
                "device": {"integration": "demo", "model": "mock-model"},
            },
            (),
            (),
        ),
    ),
)
def test_target_selector_schema(schema, valid_selections, invalid_selections):
    """Test target selector."""
    _test_selector("target", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (({}, ("abc123",), ()),),
)
def test_action_selector_schema(schema, valid_selections, invalid_selections):
    """Test action sequence selector."""
    _test_selector("action", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (({}, ("abc123",), ()),),
)
def test_object_selector_schema(schema, valid_selections, invalid_selections):
    """Test object selector."""
    _test_selector("object", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        ({}, ("abc123",), (None,)),
        ({"multiline": True}, (), ()),
        ({"multiline": False}, (), ()),
    ),
)
def test_text_selector_schema(schema, valid_selections, invalid_selections):
    """Test text selector."""
    _test_selector("text", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {"options": ["red", "green", "blue"]},
            ("red", "green", "blue"),
            ("cat", 0, None),
        ),
    ),
)
def test_select_selector_schema(schema, valid_selections, invalid_selections):
    """Test select selector."""
    _test_selector("select", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema",
    (
        {},
        {"options": {"hello": "World"}},
        {"options": []},
    ),
)
def test_select_selector_schema_error(schema):
    """Test select selector."""
    with pytest.raises(vol.Invalid):
        selector.validate_selector({"select": schema})

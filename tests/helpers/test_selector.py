"""Test selectors."""
from enum import Enum

import pytest
import voluptuous as vol

from homeassistant.helpers import selector
from homeassistant.util import yaml

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


def _test_selector(
    selector_type, schema, valid_selections, invalid_selections, converter=None
):
    """Help test a selector."""

    def default_converter(x):
        return x

    if converter is None:
        converter = default_converter

    # Validate selector configuration
    config = {selector_type: schema}
    selector.validate_selector(config)
    selector_instance = selector.selector(config)
    # We do not allow enums in the config, as they cannot serialize
    assert not any(isinstance(val, Enum) for val in selector_instance.config.values())

    # Use selector in schema and validate
    vol_schema = vol.Schema({"selection": selector_instance})
    for selection in valid_selections:
        assert vol_schema({"selection": selection}) == {
            "selection": converter(selection)
        }
    for selection in invalid_selections:
        with pytest.raises(vol.Invalid):
            vol_schema({"selection": selection})

    # Serialize selector
    selector_instance = selector.selector({selector_type: schema})
    assert (
        selector.selector(selector_instance.serialize()["selector"]).config
        == selector_instance.config
    )
    # Test serialized selector can be dumped to YAML
    yaml.dump(selector_instance.serialize())


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
        (
            {"multiple": True},
            (["abc123", "def456"],),
            ("abc123", None, ["abc123", None]),
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
        (
            {"domain": ["light", "sensor"]},
            ("light.abc123", "sensor.abc123", FAKE_UUID),
            (None, "dog.abc123"),
        ),
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
        (
            {"multiple": True, "domain": "sensor"},
            (["sensor.abc123", "sensor.def456"], ["sensor.abc123", FAKE_UUID]),
            (
                "sensor.abc123",
                FAKE_UUID,
                None,
                "abc123",
                ["sensor.abc123", "light.def456"],
            ),
        ),
        (
            {
                "include_entities": ["sensor.abc123", "sensor.def456", "sensor.ghi789"],
                "exclude_entities": ["sensor.ghi789", "sensor.jkl123"],
            },
            ("sensor.abc123", FAKE_UUID),
            ("sensor.ghi789", "sensor.jkl123"),
        ),
        (
            {
                "multiple": True,
                "include_entities": ["sensor.abc123", "sensor.def456", "sensor.ghi789"],
                "exclude_entities": ["sensor.ghi789", "sensor.jkl123"],
            },
            (["sensor.abc123", "sensor.def456"], ["sensor.abc123", FAKE_UUID]),
            (
                ["sensor.abc123", "sensor.jkl123"],
                ["sensor.abc123", "sensor.ghi789"],
            ),
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
        (
            {"multiple": True},
            ((["abc123", "def456"],)),
            (None, "abc123", ["abc123", None]),
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
        ({"mode": "box"}, (10,), ()),
    ),
)
def test_number_selector_schema(schema, valid_selections, invalid_selections):
    """Test number selector."""
    _test_selector("number", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema",
    (
        {},  # Must have mandatory fields
        {"mode": "slider"},  # Must have min+max in slider mode
    ),
)
def test_number_selector_schema_error(schema):
    """Test number selector."""
    with pytest.raises(vol.Invalid):
        selector.validate_selector({"number": schema})


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
    _test_selector(
        "boolean",
        schema,
        valid_selections,
        invalid_selections,
        bool,
    )


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            ("6b68b250388cbe0d620c92dd3acc93ec", "76f2e8f9a6491a1b580b3a8967c27ddd"),
            (None, True, 1),
        ),
        (
            {"integration": "adguard"},
            ("6b68b250388cbe0d620c92dd3acc93ec", "76f2e8f9a6491a1b580b3a8967c27ddd"),
            (None, True, 1),
        ),
    ),
)
def test_config_entry_selector_schema(schema, valid_selections, invalid_selections):
    """Test boolean selector."""
    _test_selector("config_entry", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (({}, ("00:00:00",), ("blah", None)),),
)
def test_time_selector_schema(schema, valid_selections, invalid_selections):
    """Test time selector."""
    _test_selector("time", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {"entity_id": "sensor.abc"},
            ("on", "armed"),
            (None, True, 1),
        ),
    ),
)
def test_state_selector_schema(schema, valid_selections, invalid_selections):
    """Test state selector."""
    _test_selector("state", schema, valid_selections, invalid_selections)


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
        ({"multiline": False, "type": "email"}, (), ()),
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
            ("cat", 0, None, ["red"]),
        ),
        (
            {
                "options": [
                    {"value": "red", "label": "Ruby Red"},
                    {"value": "green", "label": "Emerald Green"},
                ]
            },
            ("red", "green"),
            ("cat", 0, None, ["red"]),
        ),
        (
            {"options": ["red", "green", "blue"], "multiple": True},
            (["red"], ["green", "blue"], []),
            ("cat", 0, None, "red"),
        ),
        (
            {
                "options": ["red", "green", "blue"],
                "multiple": True,
                "custom_value": True,
            },
            (["red"], ["green", "blue"], ["red", "cat"], []),
            ("cat", 0, None, "red"),
        ),
        (
            {"options": ["red", "green", "blue"], "custom_value": True},
            ("red", "green", "blue", "cat"),
            (0, None, ["red"]),
        ),
        (
            {"options": [], "custom_value": True},
            ("red", "cat"),
            (0, None, ["red"]),
        ),
        (
            {"options": [], "custom_value": True, "multiple": True, "mode": "list"},
            (["red"], ["green", "blue"], []),
            (0, None, "red"),
        ),
    ),
)
def test_select_selector_schema(schema, valid_selections, invalid_selections):
    """Test select selector."""
    _test_selector("select", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema",
    (
        {},  # Must have options
        {"options": {"hello": "World"}},  # Options must be a list
        # Options must be strings or value / label pairs
        {"options": [{"hello": "World"}]},
        # Options must all be of the same type
        {"options": ["red", {"value": "green", "label": "Emerald Green"}]},
    ),
)
def test_select_selector_schema_error(schema):
    """Test select selector."""
    with pytest.raises(vol.Invalid):
        selector.validate_selector({"select": schema})


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {"entity_id": "sensor.abc"},
            ("friendly_name", "device_class"),
            (None,),
        ),
        (
            {"entity_id": "sensor.abc", "hide_attributes": ["friendly_name"]},
            ("device_class", "state_class"),
            (None,),
        ),
    ),
)
def test_attribute_selector_schema(schema, valid_selections, invalid_selections):
    """Test attribute selector."""
    _test_selector("attribute", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            (
                {"seconds": 10},
                {"days": 10},  # Days is allowed also if `enable_day` is not set
            ),
            (None, {}),
        ),
        (
            {"enable_day": True},
            ({"seconds": 10}, {"days": 10}),
            (None, {}),
        ),
    ),
)
def test_duration_selector_schema(schema, valid_selections, invalid_selections):
    """Test duration selector."""
    _test_selector("duration", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            ("mdi:abc",),
            (None,),
        ),
    ),
)
def test_icon_selector_schema(schema, valid_selections, invalid_selections):
    """Test icon selector."""
    _test_selector("icon", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            ("abc",),
            (None,),
        ),
    ),
)
def test_theme_selector_schema(schema, valid_selections, invalid_selections):
    """Test theme selector."""
    _test_selector("theme", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            (
                {
                    "entity_id": "sensor.abc",
                    "media_content_id": "abc",
                    "media_content_type": "def",
                },
                {
                    "entity_id": "sensor.abc",
                    "media_content_id": "abc",
                    "media_content_type": "def",
                    "metadata": {},
                },
            ),
            (None, "abc", {}),
        ),
    ),
)
def test_media_selector_schema(schema, valid_selections, invalid_selections):
    """Test media selector."""

    def drop_metadata(data):
        """Drop metadata key from the input."""
        data.pop("metadata", None)
        return data

    _test_selector(
        "media",
        schema,
        valid_selections,
        invalid_selections,
        drop_metadata,
    )


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            (
                {
                    "latitude": 1.0,
                    "longitude": 2.0,
                },
                {
                    "latitude": 1.0,
                    "longitude": 2.0,
                    "radius": 3.0,
                },
            ),
            (
                None,
                "abc",
                {},
                {"latitude": 1.0},
                {"longitude": 1.0},
                {"latitude": 1.0, "longitude": "1.0"},
            ),
        ),
    ),
)
def test_location_selector_schema(schema, valid_selections, invalid_selections):
    """Test location selector."""

    _test_selector("location", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            ([0, 0, 0], [255, 255, 255], [0.0, 0.0, 0.0], [255.0, 255.0, 255.0]),
            (None, "abc", [0, 0, "nil"], (255, 255, 255)),
        ),
    ),
)
def test_rgb_color_selector_schema(schema, valid_selections, invalid_selections):
    """Test color_rgb selector."""

    _test_selector("color_rgb", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            (100, 100.0),
            (None, "abc", [100]),
        ),
        (
            {"min_mireds": 100, "max_mireds": 200},
            (100, 200),
            (99, 201),
        ),
    ),
)
def test_color_tempselector_schema(schema, valid_selections, invalid_selections):
    """Test color_temp selector."""

    _test_selector("color_temp", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            ("2022-03-24",),
            (None, "abc", "00:00", "2022-03-24 00:00", "2022-03-32"),
        ),
    ),
)
def test_date_selector_schema(schema, valid_selections, invalid_selections):
    """Test date selector."""

    _test_selector("date", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {},
            ("2022-03-24 00:00", "2022-03-24"),
            (None, "abc", "00:00", "2022-03-24 24:01"),
        ),
    ),
)
def test_datetime_selector_schema(schema, valid_selections, invalid_selections):
    """Test datetime selector."""

    _test_selector("datetime", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (({}, ("abc123", "{{ now() }}"), (None, "{{ incomplete }", "{% if True %}Hi!")),),
)
def test_template_selector_schema(schema, valid_selections, invalid_selections):
    """Test template selector."""
    _test_selector("template", schema, valid_selections, invalid_selections)


@pytest.mark.parametrize(
    "schema,valid_selections,invalid_selections",
    (
        (
            {"accept": "image/*"},
            ("0182a1b99dbc5ae24aecd90c346605fa",),
            (None, "not-a-uuid", "abcd", 1),
        ),
    ),
)
def test_file_selector_schema(schema, valid_selections, invalid_selections):
    """Test file selector."""

    _test_selector("file", schema, valid_selections, invalid_selections)

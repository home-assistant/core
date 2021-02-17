"""Test selectors."""
import pytest
import voluptuous as vol

from homeassistant.helpers import selector


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


@pytest.mark.parametrize(
    "schema",
    (
        {},
        {"integration": "zha"},
        {"manufacturer": "mock-manuf"},
        {"model": "mock-model"},
        {"manufacturer": "mock-manuf", "model": "mock-model"},
        {"integration": "zha", "manufacturer": "mock-manuf", "model": "mock-model"},
        {"entity": {"device_class": "motion"}},
        {
            "integration": "zha",
            "manufacturer": "mock-manuf",
            "model": "mock-model",
            "entity": {"domain": "binary_sensor", "device_class": "motion"},
        },
    ),
)
def test_device_selector_schema(schema):
    """Test device selector."""
    selector.validate_selector({"device": schema})


@pytest.mark.parametrize(
    "schema",
    (
        {},
        {"integration": "zha"},
        {"domain": "light"},
        {"device_class": "motion"},
        {"integration": "zha", "domain": "light"},
        {"integration": "zha", "domain": "binary_sensor", "device_class": "motion"},
    ),
)
def test_entity_selector_schema(schema):
    """Test entity selector."""
    selector.validate_selector({"entity": schema})


@pytest.mark.parametrize(
    "schema",
    (
        {},
        {"entity": {}},
        {"entity": {"domain": "light"}},
        {"entity": {"domain": "binary_sensor", "device_class": "motion"}},
        {
            "entity": {
                "domain": "binary_sensor",
                "device_class": "motion",
                "integration": "demo",
            }
        },
        {"device": {"integration": "demo", "model": "mock-model"}},
        {
            "entity": {"domain": "binary_sensor", "device_class": "motion"},
            "device": {"integration": "demo", "model": "mock-model"},
        },
    ),
)
def test_area_selector_schema(schema):
    """Test area selector."""
    selector.validate_selector({"area": schema})


@pytest.mark.parametrize(
    "schema",
    (
        {"min": 10, "max": 50},
        {"min": -100, "max": 100, "step": 5},
        {"min": -20, "max": -10, "mode": "box"},
        {"min": 0, "max": 100, "unit_of_measurement": "seconds", "mode": "slider"},
        {"min": 10, "max": 1000, "mode": "slider", "step": 0.5},
    ),
)
def test_number_selector_schema(schema):
    """Test number selector."""
    selector.validate_selector({"number": schema})


@pytest.mark.parametrize(
    "schema",
    ({},),
)
def test_boolean_selector_schema(schema):
    """Test boolean selector."""
    selector.validate_selector({"boolean": schema})


@pytest.mark.parametrize(
    "schema",
    ({},),
)
def test_time_selector_schema(schema):
    """Test time selector."""
    selector.validate_selector({"time": schema})


@pytest.mark.parametrize(
    "schema",
    (
        {},
        {"entity": {}},
        {"entity": {"domain": "light"}},
        {"entity": {"domain": "binary_sensor", "device_class": "motion"}},
        {
            "entity": {
                "domain": "binary_sensor",
                "device_class": "motion",
                "integration": "demo",
            }
        },
        {"device": {"integration": "demo", "model": "mock-model"}},
        {
            "entity": {"domain": "binary_sensor", "device_class": "motion"},
            "device": {"integration": "demo", "model": "mock-model"},
        },
    ),
)
def test_target_selector_schema(schema):
    """Test target selector."""
    selector.validate_selector({"target": schema})


@pytest.mark.parametrize(
    "schema",
    ({},),
)
def test_action_selector_schema(schema):
    """Test action sequence selector."""
    selector.validate_selector({"action": schema})


@pytest.mark.parametrize(
    "schema",
    ({},),
)
def test_object_selector_schema(schema):
    """Test object selector."""
    selector.validate_selector({"object": schema})


@pytest.mark.parametrize(
    "schema",
    ({}, {"multiline": True}, {"multiline": False}),
)
def test_text_selector_schema(schema):
    """Test text selector."""
    selector.validate_selector({"text": schema})


@pytest.mark.parametrize(
    "schema",
    ({"options": ["red", "green", "blue"]},),
)
def test_select_selector_schema(schema):
    """Test select selector."""
    selector.validate_selector({"select": schema})


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

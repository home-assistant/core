"""Test selectors."""
import pytest
import voluptuous as vol

from homeassistant.helpers import selector


@pytest.mark.parametrize(
    "schema", ({}, {"non_existing": {}}, {"device": {}, "entity": {}})
)
def test_invalid_base_schema(schema):
    """Test base schema validation."""
    with pytest.raises(vol.Invalid):
        selector.validate_selector(schema)


@pytest.mark.parametrize(
    "schema",
    (
        {},
        {"integration": "zha"},
        {"manufacturer": "mock-manuf"},
        {"model": "mock-model"},
        {"manufacturer": "mock-manuf", "model": "mock-model"},
        {"integration": "zha", "manufacturer": "mock-manuf", "model": "mock-model"},
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
        {"integration": "zha", "domain": "light"},
    ),
)
def test_entity_selector_schema(schema):
    """Test device selector."""
    selector.validate_selector({"entity": schema})

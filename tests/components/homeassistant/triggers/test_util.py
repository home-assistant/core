"""The test for trigger util."""

import pytest
import voluptuous as vol

from homeassistant.components.homeassistant.triggers.util import (
    validate_entities_or_template_of_entities,
)
from homeassistant.helpers import template


def test_validate_entity_or_template_of_entities():
    """Test Template or entity ID validation."""
    schema = vol.Schema(validate_entities_or_template_of_entities)

    options = (
        None,
        "invalid_entity",
        "sensor.light,sensor_invalid",
        ["invalid_entity"],
        ["sensor.light", "sensor_invalid"],
        ["sensor.light,sensor_invalid"],
        "sensor.light,{{more}}",
        "{{get_ids}",
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        [],
        ["sensor.light"],
        "sensor.light",
        "{{get_ids}}",
        "{{get_ids}},sensor.light",
    )
    for value in options:
        schema(value)

    assert schema("sensor.LIGHT, light.kitchen ") == ["sensor.light", "light.kitchen"]
    assert isinstance(schema("{{get_ids}}"), template.Template)

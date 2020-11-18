"""Test schemas."""
import logging

import pytest
import voluptuous as vol

from homeassistant.components.blueprint import schemas

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "blueprint",
    (
        # Test allow extra
        {
            "trigger": "Test allow extra",
            "blueprint": {"name": "Test Name", "domain": "automation"},
        },
        # Bare minimum
        {"blueprint": {"name": "Test Name", "domain": "automation"}},
        # Empty triggers
        {"blueprint": {"name": "Test Name", "domain": "automation", "input": {}}},
        # No definition of input
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "input": {
                    "some_placeholder": None,
                },
            }
        },
        # With selector
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "input": {
                    "some_placeholder": {"selector": {"entity": {}}},
                },
            }
        },
        # With min version
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "homeassistant": {
                    "min_version": "1000000.0.0",
                },
            }
        },
    ),
)
def test_blueprint_schema(blueprint):
    """Test different schemas."""
    try:
        schemas.BLUEPRINT_SCHEMA(blueprint)
    except vol.Invalid:
        _LOGGER.exception("%s", blueprint)
        assert False, "Expected schema to be valid"


@pytest.mark.parametrize(
    "blueprint",
    (
        # no domain
        {"blueprint": {}},
        # non existing key in blueprint
        {
            "blueprint": {
                "name": "Example name",
                "domain": "automation",
                "non_existing": None,
            }
        },
        # non existing key in input
        {
            "blueprint": {
                "name": "Example name",
                "domain": "automation",
                "input": {"some_placeholder": {"non_existing": "bla"}},
            }
        },
        # Invalid version
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "homeassistant": {
                    "min_version": "1000000.invalid.0",
                },
            }
        },
    ),
)
def test_blueprint_schema_invalid(blueprint):
    """Test different schemas."""
    with pytest.raises(vol.Invalid):
        schemas.BLUEPRINT_SCHEMA(blueprint)

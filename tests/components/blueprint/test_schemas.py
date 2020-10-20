"""Test schemas."""
import logging

import voluptuous as vol

from homeassistant.components.blueprint import schemas

_LOGGER = logging.getLogger(__name__)


def test_blueprint_schema():
    """Test different schemas."""
    for valid_blueprint in (
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
    ):
        try:
            schemas.BLUEPRINT_SCHEMA(valid_blueprint)
        except vol.Invalid:
            _LOGGER.exception("%s", valid_blueprint)
            assert False, "Expected schema to be valid"

    for invalid_blueprint in (
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
    ):
        try:
            schemas.BLUEPRINT_SCHEMA(invalid_blueprint)
            _LOGGER.error("%s", invalid_blueprint)
            assert False, "Expected schema to be invalid"
        except vol.Invalid:
            pass

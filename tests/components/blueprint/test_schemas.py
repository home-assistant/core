"""Test schemas."""

import logging

import probatio
import pytest

from homeassistant.components.blueprint import schemas

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "blueprint",
    [
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
        # With input sections
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "input": {
                    "section_a": {
                        "input": {"some_placeholder": None},
                    },
                    "section_b": {
                        "name": "Section",
                        "description": "A section with no inputs",
                        "input": {},
                    },
                    "some_placeholder_2": None,
                },
            }
        },
    ],
)
def test_blueprint_schema(blueprint) -> None:
    """Test different schemas."""
    try:
        schemas.BLUEPRINT_SCHEMA(blueprint)
    except probatio.Invalid:
        _LOGGER.exception("%s", blueprint)
        pytest.fail("Expected schema to be valid")


def test_blueprint_schema_selector_context() -> None:
    """Test a selector context referring to other inputs is kept."""
    uom_selector = {
        "unit_of_measurement": {
            "context": {
                "filter_device_class": "device_class",
                "filter_state_class": "state_class",
            }
        }
    }
    blueprint = schemas.BLUEPRINT_SCHEMA(
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "input": {
                    "device_class": {
                        "selector": {"device_class": {"domain": "sensor"}}
                    },
                    "state_class": {"selector": {"state_class": {}}},
                    "unit": {"selector": uom_selector},
                },
            }
        }
    )
    assert blueprint["blueprint"]["input"]["unit"]["selector"] == uom_selector


@pytest.mark.parametrize(
    "blueprint",
    [
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
        # Selector context key not allowed by the selector
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "input": {
                    "unit": {
                        "selector": {
                            "unit_of_measurement": {
                                "context": {"filter_entity": "entity_id"}
                            }
                        }
                    },
                },
            }
        },
        # Duplicate inputs in sections (1 of 2)
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "input": {
                    "section_a": {
                        "input": {"some_placeholder": None},
                    },
                    "section_b": {
                        "input": {"some_placeholder": None},
                    },
                },
            }
        },
        # Duplicate inputs in sections (2 of 2)
        {
            "blueprint": {
                "name": "Test Name",
                "domain": "automation",
                "input": {
                    "section_a": {
                        "input": {"some_placeholder": None},
                    },
                    "some_placeholder": None,
                },
            }
        },
    ],
)
def test_blueprint_schema_invalid(blueprint) -> None:
    """Test different schemas."""
    with pytest.raises(probatio.Invalid):
        schemas.BLUEPRINT_SCHEMA(blueprint)


@pytest.mark.parametrize(
    "bp_instance",
    [
        {"path": "hello.yaml"},
        {"path": "hello.yaml", "input": {}},
        {"path": "hello.yaml", "input": {"hello": None}},
    ],
)
def test_blueprint_instance_fields(bp_instance) -> None:
    """Test blueprint instance fields."""
    schemas.BLUEPRINT_INSTANCE_FIELDS({"use_blueprint": bp_instance})

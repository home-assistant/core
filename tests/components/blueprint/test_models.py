"""Test blueprint models."""

from collections.abc import Callable
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.blueprint import BLUEPRINT_SCHEMA, errors, models
from homeassistant.config import _get_annotation
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import Input
from homeassistant.util.yaml.objects import NodeDictClass, NodeListClass, NodeStrClass

from tests.common import get_test_config_dir

# A real blueprint in the test config dir, loaded from disk by DomainBlueprints.
BLUEPRINT_PATH = "test_event_sensor.yaml"
BLUEPRINT_FILE = get_test_config_dir("blueprints", "template", BLUEPRINT_PATH)

SUBSTITUTE_XFAIL = pytest.mark.xfail(
    strict=True,
    reason=(
        "annotatedyaml's substitute (input.py:51,54) rebuilds containers with "
        "comprehensions, so the node class and the __config_file__/__line__ slots "
        "are both dropped"
    ),
)


@pytest.fixture
def blueprint_1() -> models.Blueprint:
    """Blueprint fixture."""
    return models.Blueprint(
        {
            "blueprint": {
                "name": "Hello",
                "domain": "automation",
                "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
                "input": {"test-input": {"name": "Name", "description": "Description"}},
            },
            "example": Input("test-input"),
        },
        schema=BLUEPRINT_SCHEMA,
    )


@pytest.fixture(params=[False, True])
def blueprint_2(request: pytest.FixtureRequest) -> models.Blueprint:
    """Blueprint fixture with default inputs."""
    blueprint = {
        "blueprint": {
            "name": "Hello",
            "domain": "automation",
            "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
            "input": {
                "test-input": {"name": "Name", "description": "Description"},
                "test-input-default": {"default": "test"},
            },
        },
        "example": Input("test-input"),
        "example-default": Input("test-input-default"),
    }
    if request.param:
        # Replace the inputs with inputs in sections.
        # Test should otherwise behave the same.
        blueprint["blueprint"]["input"] = {
            "section-1": {
                "name": "Section 1",
                "input": {
                    "test-input": {"name": "Name", "description": "Description"},
                },
            },
            "section-2": {
                "input": {
                    "test-input-default": {"default": "test"},
                }
            },
        }
    return models.Blueprint(blueprint, schema=BLUEPRINT_SCHEMA)


@pytest.fixture
async def yaml_blueprint(hass: HomeAssistant) -> models.Blueprint:
    """Blueprint loaded from a real YAML file, so its nodes carry source annotations."""
    domain_bps = models.DomainBlueprints(
        hass,
        "template",
        logging.getLogger(__name__),
        None,
        AsyncMock(),
        BLUEPRINT_SCHEMA,
    )
    return await domain_bps.async_get_blueprint(BLUEPRINT_PATH)


@pytest.fixture
def yaml_blueprint_inputs(
    yaml_blueprint: models.Blueprint,
) -> models.BlueprintInputs:
    """Validated inputs for the YAML blueprint fixture."""
    inputs = models.BlueprintInputs(
        yaml_blueprint,
        {
            "use_blueprint": {
                "path": BLUEPRINT_PATH,
                "input": {
                    "event_type": "my_event",
                    "event_data": {"hello": "world"},
                },
            }
        },
    )
    inputs.validate()
    return inputs


@pytest.fixture
def domain_bps(hass: HomeAssistant) -> models.DomainBlueprints:
    """Domain blueprints fixture."""
    return models.DomainBlueprints(
        hass,
        "automation",
        logging.getLogger(__name__),
        None,
        AsyncMock(),
        BLUEPRINT_SCHEMA,
    )


def test_blueprint_model_init() -> None:
    """Test constructor validation."""
    with pytest.raises(errors.InvalidBlueprint):
        models.Blueprint({}, schema=BLUEPRINT_SCHEMA)

    with pytest.raises(errors.InvalidBlueprint):
        models.Blueprint(
            {"blueprint": {"name": "Hello", "domain": "automation"}},
            expected_domain="not-automation",
            schema=BLUEPRINT_SCHEMA,
        )

    with pytest.raises(errors.InvalidBlueprint):
        models.Blueprint(
            {
                "blueprint": {
                    "name": "Hello",
                    "domain": "automation",
                    "input": {"something": None},
                },
                "trigger": {"platform": Input("non-existing")},
            },
            schema=BLUEPRINT_SCHEMA,
        )


def test_blueprint_properties(blueprint_1: models.Blueprint) -> None:
    """Test properties."""
    assert blueprint_1.metadata == {
        "name": "Hello",
        "domain": "automation",
        "source_url": "https://github.com/balloob/home-assistant-config/blob/main/blueprints/automation/motion_light.yaml",
        "input": {"test-input": {"name": "Name", "description": "Description"}},
    }
    assert blueprint_1.domain == "automation"
    assert blueprint_1.name == "Hello"
    assert blueprint_1.inputs == {
        "test-input": {"name": "Name", "description": "Description"}
    }


def test_blueprint_update_metadata() -> None:
    """Test update metadata."""
    bp = models.Blueprint(
        {
            "blueprint": {
                "name": "Hello",
                "domain": "automation",
            },
        },
        schema=BLUEPRINT_SCHEMA,
    )

    bp.update_metadata(source_url="http://bla.com")
    assert bp.metadata["source_url"] == "http://bla.com"


def test_blueprint_validate() -> None:
    """Test validate blueprint."""
    assert (
        models.Blueprint(
            {
                "blueprint": {
                    "name": "Hello",
                    "domain": "automation",
                },
            },
            schema=BLUEPRINT_SCHEMA,
        ).validate()
        is None
    )

    assert models.Blueprint(
        {
            "blueprint": {
                "name": "Hello",
                "domain": "automation",
                "homeassistant": {"min_version": "100000.0.0"},
            },
        },
        schema=BLUEPRINT_SCHEMA,
    ).validate() == ["Requires at least Home Assistant 100000.0.0"]


def test_blueprint_inputs(blueprint_2: models.Blueprint) -> None:
    """Test blueprint inputs."""
    inputs = models.BlueprintInputs(
        blueprint_2,
        {
            "use_blueprint": {
                "path": "bla",
                "input": {"test-input": 1, "test-input-default": 12},
            },
            "example-default": {"overridden": "via-config"},
        },
    )
    inputs.validate()
    assert inputs.inputs == {"test-input": 1, "test-input-default": 12}
    assert inputs.async_substitute() == {
        "example": 1,
        "example-default": {"overridden": "via-config"},
    }


def test_blueprint_inputs_validation(blueprint_1: models.Blueprint) -> None:
    """Test blueprint input validation."""
    inputs = models.BlueprintInputs(
        blueprint_1,
        {"use_blueprint": {"path": "bla", "input": {"non-existing-placeholder": 1}}},
    )
    with pytest.raises(errors.MissingInput):
        inputs.validate()


def test_blueprint_inputs_default(blueprint_2: models.Blueprint) -> None:
    """Test blueprint inputs."""
    inputs = models.BlueprintInputs(
        blueprint_2,
        {"use_blueprint": {"path": "bla", "input": {"test-input": 1}}},
    )
    inputs.validate()
    assert inputs.inputs == {"test-input": 1}
    assert inputs.inputs_with_default == {
        "test-input": 1,
        "test-input-default": "test",
    }
    assert inputs.async_substitute() == {"example": 1, "example-default": "test"}


def test_blueprint_inputs_override_default(blueprint_2: models.Blueprint) -> None:
    """Test blueprint inputs."""
    inputs = models.BlueprintInputs(
        blueprint_2,
        {
            "use_blueprint": {
                "path": "bla",
                "input": {"test-input": 1, "test-input-default": "custom"},
            }
        },
    )
    inputs.validate()
    assert inputs.inputs == {
        "test-input": 1,
        "test-input-default": "custom",
    }
    assert inputs.inputs_with_default == {
        "test-input": 1,
        "test-input-default": "custom",
    }
    assert inputs.async_substitute() == {"example": 1, "example-default": "custom"}


def test_yaml_blueprint_keeps_annotations_through_the_schema(
    yaml_blueprint: models.Blueprint,
) -> None:
    """Test the blueprint schema hands the config through with its annotations.

    BLUEPRINT_SCHEMA allows extra keys, and probatio stores the original value
    object for those, so anything missing after async_substitute was dropped by
    the substitution rather than by the schema.
    """
    data = yaml_blueprint.data

    assert type(data["triggers"]) is NodeListClass
    assert _get_annotation(data["triggers"]) == (BLUEPRINT_FILE, 18)
    assert _get_annotation(data["triggers"][0]) == (BLUEPRINT_FILE, 18)
    assert _get_annotation(data["sensor"]) == (BLUEPRINT_FILE, 24)
    assert _get_annotation(data["sensor"]["attributes"]) == (BLUEPRINT_FILE, 27)


@pytest.mark.parametrize(
    ("select", "expected_type", "expected_annotation"),
    [
        pytest.param(
            lambda config: next(key for key in config if key == "triggers"),
            NodeStrClass,
            (BLUEPRINT_FILE, 17),
            id="key_at_root",
        ),
        pytest.param(
            lambda config: next(
                key for key in config["triggers"][0] if key == "trigger"
            ),
            NodeStrClass,
            (BLUEPRINT_FILE, 18),
            id="key_in_list_element",
        ),
        pytest.param(
            lambda config: config["triggers"],
            NodeListClass,
            (BLUEPRINT_FILE, 18),
            marks=SUBSTITUTE_XFAIL,
            id="list_in_dict",
        ),
        pytest.param(
            lambda config: config["triggers"][0],
            NodeDictClass,
            (BLUEPRINT_FILE, 18),
            marks=SUBSTITUTE_XFAIL,
            id="dict_in_list",
        ),
        pytest.param(
            lambda config: config["sensor"],
            NodeDictClass,
            (BLUEPRINT_FILE, 24),
            marks=SUBSTITUTE_XFAIL,
            id="dict_in_dict",
        ),
        pytest.param(
            lambda config: config["sensor"]["attributes"],
            NodeDictClass,
            (BLUEPRINT_FILE, 27),
            marks=SUBSTITUTE_XFAIL,
            id="dict_in_dict_in_dict",
        ),
    ],
)
def test_substituted_blueprint_keeps_annotations(
    yaml_blueprint_inputs: models.BlueprintInputs,
    select: Callable[[dict], Any],
    expected_type: type,
    expected_annotation: tuple[str, int],
) -> None:
    """Test the substituted config keeps the node classes and their locations.

    The keys pass today because substitute's dict comprehension hands them
    through unchanged, which is the only reason a blueprint-backed config still
    reports where an error came from. The result's top level is deliberately not
    asserted: async_substitute merges it into a fresh dict literal, so it can
    never carry an annotation.
    """
    config = yaml_blueprint_inputs.async_substitute()
    node = select(config)

    assert type(node) is expected_type
    assert _get_annotation(node) == expected_annotation


async def test_domain_blueprints_get_blueprint_errors(
    hass: HomeAssistant, domain_bps: models.DomainBlueprints
) -> None:
    """Test domain blueprints."""
    assert hass.data["blueprint"]["automation"] is domain_bps

    with (
        pytest.raises(errors.FailedToLoad),
        patch("homeassistant.util.yaml.load_yaml", side_effect=FileNotFoundError),
    ):
        await domain_bps.async_get_blueprint("non-existing-path")

    with (
        patch(
            "homeassistant.util.yaml.load_yaml", return_value={"blueprint": "invalid"}
        ),
        pytest.raises(errors.FailedToLoad),
    ):
        await domain_bps.async_get_blueprint("non-existing-path")


async def test_domain_blueprints_caching(domain_bps: models.DomainBlueprints) -> None:
    """Test domain blueprints cache blueprints."""
    obj = object()
    with patch.object(domain_bps, "_load_blueprint", return_value=obj):
        assert await domain_bps.async_get_blueprint("something") is obj

    # Now we hit cache
    assert await domain_bps.async_get_blueprint("something") is obj

    obj_2 = object()
    await domain_bps.async_reset_cache()

    # Now we call this method again.
    with patch.object(domain_bps, "_load_blueprint", return_value=obj_2):
        assert await domain_bps.async_get_blueprint("something") is obj_2


async def test_domain_blueprints_inputs_from_config(
    domain_bps: models.DomainBlueprints, blueprint_1: models.Blueprint
) -> None:
    """Test DomainBlueprints.async_inputs_from_config."""
    with pytest.raises(errors.InvalidBlueprintInputs):
        await domain_bps.async_inputs_from_config({"not-referencing": "use_blueprint"})

    with (
        pytest.raises(errors.MissingInput),
        patch.object(domain_bps, "async_get_blueprint", return_value=blueprint_1),
    ):
        await domain_bps.async_inputs_from_config(
            {"use_blueprint": {"path": "bla.yaml", "input": {}}}
        )

    with patch.object(domain_bps, "async_get_blueprint", return_value=blueprint_1):
        inputs = await domain_bps.async_inputs_from_config(
            {"use_blueprint": {"path": "bla.yaml", "input": {"test-input": None}}}
        )
    assert inputs.blueprint is blueprint_1
    assert inputs.inputs == {"test-input": None}


async def test_domain_blueprints_add_blueprint(
    domain_bps: models.DomainBlueprints, blueprint_1: models.Blueprint
) -> None:
    """Test DomainBlueprints.async_add_blueprint."""
    with patch.object(domain_bps, "_create_file") as create_file_mock:
        await domain_bps.async_add_blueprint(blueprint_1, "something.yaml")
        assert create_file_mock.call_args[0][1] == "something.yaml"

    # Should be in cache.
    with patch.object(domain_bps, "_load_blueprint") as mock_load:
        assert await domain_bps.async_get_blueprint("something.yaml") == blueprint_1
        assert not mock_load.mock_calls


async def test_inputs_from_config_nonexisting_blueprint(
    domain_bps: models.DomainBlueprints,
) -> None:
    """Test referring non-existing blueprint."""
    with pytest.raises(errors.FailedToLoad):
        await domain_bps.async_inputs_from_config(
            {"use_blueprint": {"path": "non-existing.yaml"}}
        )

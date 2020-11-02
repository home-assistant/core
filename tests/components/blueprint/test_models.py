"""Test blueprint models."""
import logging

import pytest

from homeassistant.components.blueprint import errors, models
from homeassistant.util.yaml import Placeholder

from tests.async_mock import patch


@pytest.fixture
def blueprint_1():
    """Blueprint fixture."""
    return models.Blueprint(
        {
            "blueprint": {
                "name": "Hello",
                "domain": "automation",
                "input": {"test-placeholder": None},
            },
            "example": Placeholder("test-placeholder"),
        }
    )


@pytest.fixture
def domain_bps(hass):
    """Domain blueprints fixture."""
    return models.DomainBlueprints(hass, "automation", logging.getLogger(__name__))


def test_blueprint_model_init():
    """Test constructor validation."""
    with pytest.raises(errors.InvalidBlueprint):
        models.Blueprint({})

    with pytest.raises(errors.InvalidBlueprint):
        models.Blueprint(
            {"blueprint": {"name": "Hello", "domain": "automation"}},
            expected_domain="not-automation",
        )

    with pytest.raises(errors.InvalidBlueprint):
        models.Blueprint(
            {
                "blueprint": {
                    "name": "Hello",
                    "domain": "automation",
                    "input": {"something": None},
                },
                "trigger": {"platform": Placeholder("non-existing")},
            }
        )


def test_blueprint_properties(blueprint_1):
    """Test properties."""
    assert blueprint_1.metadata == {
        "name": "Hello",
        "domain": "automation",
        "input": {"test-placeholder": None},
    }
    assert blueprint_1.domain == "automation"
    assert blueprint_1.name == "Hello"
    assert blueprint_1.placeholders == {"test-placeholder"}


def test_blueprint_update_metadata():
    """Test properties."""
    bp = models.Blueprint(
        {
            "blueprint": {
                "name": "Hello",
                "domain": "automation",
            },
        }
    )

    bp.update_metadata(source_url="http://bla.com")
    assert bp.metadata["source_url"] == "http://bla.com"


def test_blueprint_inputs(blueprint_1):
    """Test blueprint inputs."""
    inputs = models.BlueprintInputs(
        blueprint_1,
        {"use_blueprint": {"path": "bla", "input": {"test-placeholder": 1}}},
    )
    inputs.validate()
    assert inputs.inputs == {"test-placeholder": 1}
    assert inputs.async_substitute() == {"example": 1}


def test_blueprint_inputs_validation(blueprint_1):
    """Test blueprint input validation."""
    inputs = models.BlueprintInputs(
        blueprint_1,
        {"use_blueprint": {"path": "bla", "input": {"non-existing-placeholder": 1}}},
    )
    with pytest.raises(errors.MissingPlaceholder):
        inputs.validate()


async def test_domain_blueprints_get_blueprint_errors(hass, domain_bps):
    """Test domain blueprints."""
    assert hass.data["blueprint"]["automation"] is domain_bps

    with pytest.raises(errors.FailedToLoad), patch(
        "homeassistant.util.yaml.load_yaml", side_effect=FileNotFoundError
    ):
        await domain_bps.async_get_blueprint("non-existing-path")

    with patch(
        "homeassistant.util.yaml.load_yaml", return_value={"blueprint": "invalid"}
    ):
        assert await domain_bps.async_get_blueprint("non-existing-path") is None


async def test_domain_blueprints_caching(domain_bps):
    """Test domain blueprints cache blueprints."""
    obj = object()
    with patch.object(domain_bps, "_load_blueprint", return_value=obj):
        assert await domain_bps.async_get_blueprint("something") is obj

    # Now we hit cache
    assert await domain_bps.async_get_blueprint("something") is obj

    obj_2 = object()
    domain_bps.async_reset_cache()

    # Now we call this method again.
    with patch.object(domain_bps, "_load_blueprint", return_value=obj_2):
        assert await domain_bps.async_get_blueprint("something") is obj_2


async def test_domain_blueprints_inputs_from_config(domain_bps, blueprint_1):
    """Test DomainBlueprints.async_inputs_from_config."""
    with pytest.raises(errors.InvalidBlueprintInputs):
        await domain_bps.async_inputs_from_config({"not-referencing": "use_blueprint"})

    with pytest.raises(errors.MissingPlaceholder), patch.object(
        domain_bps, "async_get_blueprint", return_value=blueprint_1
    ):
        await domain_bps.async_inputs_from_config(
            {"use_blueprint": {"path": "bla.yaml", "input": {}}}
        )

    with patch.object(domain_bps, "async_get_blueprint", return_value=blueprint_1):
        inputs = await domain_bps.async_inputs_from_config(
            {"use_blueprint": {"path": "bla.yaml", "input": {"test-placeholder": None}}}
        )
    assert inputs.blueprint is blueprint_1
    assert inputs.inputs == {"test-placeholder": None}

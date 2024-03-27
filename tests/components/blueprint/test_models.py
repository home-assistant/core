"""Test blueprint models."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.blueprint import errors, models
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml import Input


@pytest.fixture
def blueprint_1():
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
        }
    )


@pytest.fixture
def blueprint_2():
    """Blueprint fixture with default inputs."""
    return models.Blueprint(
        {
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
    )


@pytest.fixture
def domain_bps(hass):
    """Domain blueprints fixture."""
    return models.DomainBlueprints(
        hass, "automation", logging.getLogger(__name__), None, AsyncMock()
    )


def test_blueprint_model_init() -> None:
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
                "trigger": {"platform": Input("non-existing")},
            }
        )


def test_blueprint_properties(blueprint_1) -> None:
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
        }
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
            }
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
        }
    ).validate() == ["Requires at least Home Assistant 100000.0.0"]


def test_blueprint_inputs(blueprint_2) -> None:
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


def test_blueprint_inputs_validation(blueprint_1) -> None:
    """Test blueprint input validation."""
    inputs = models.BlueprintInputs(
        blueprint_1,
        {"use_blueprint": {"path": "bla", "input": {"non-existing-placeholder": 1}}},
    )
    with pytest.raises(errors.MissingInput):
        inputs.validate()


def test_blueprint_inputs_default(blueprint_2) -> None:
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


def test_blueprint_inputs_override_default(blueprint_2) -> None:
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


async def test_domain_blueprints_get_blueprint_errors(
    hass: HomeAssistant, domain_bps
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


async def test_domain_blueprints_caching(domain_bps) -> None:
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


async def test_domain_blueprints_inputs_from_config(domain_bps, blueprint_1) -> None:
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


async def test_domain_blueprints_add_blueprint(domain_bps, blueprint_1) -> None:
    """Test DomainBlueprints.async_add_blueprint."""
    with patch.object(domain_bps, "_create_file") as create_file_mock:
        await domain_bps.async_add_blueprint(blueprint_1, "something.yaml")
        assert create_file_mock.call_args[0][1] == "something.yaml"

    # Should be in cache.
    with patch.object(domain_bps, "_load_blueprint") as mock_load:
        assert await domain_bps.async_get_blueprint("something.yaml") == blueprint_1
        assert not mock_load.mock_calls


async def test_inputs_from_config_nonexisting_blueprint(domain_bps) -> None:
    """Test referring non-existing blueprint."""
    with pytest.raises(errors.FailedToLoad):
        await domain_bps.async_inputs_from_config(
            {"use_blueprint": {"path": "non-existing.yaml"}}
        )

"""Tests for hassfest core_files validation."""

from pathlib import Path
from unittest.mock import patch

from script.hassfest.core_files import EXTRA_BASE_PLATFORMS, validate
from script.hassfest.model import Config, Integration


def _create_integration(
    config: Config, domain: str, integration_type: str = "hub"
) -> Integration:
    """Create a minimal Integration with the given type."""
    integration = Integration(config.core_integrations_path / domain, _config=config)

    integration._manifest = {
        "domain": domain,
        "name": domain,
        "integration_type": integration_type,
    }
    return integration


def _create_core_files_yaml(base_platforms: list[str]) -> dict:
    """Build a minimal .core_files.yaml dict."""
    return {
        "base_platforms": [f"homeassistant/components/{p}/**" for p in base_platforms],
    }


def test_skip_specific_integrations() -> None:
    """Test that validation is skipped for specific integrations."""
    config = Config(
        root=Path(".").absolute(),
        specific_integrations=[Path("some/path")],
        action="validate",
        requirements=False,
    )
    # Should not raise or add errors — it just returns early
    validate({}, config)
    assert not config.errors


def test_valid_alignment(config: Config) -> None:
    """Test no errors when base_platforms matches entity platforms."""
    integrations = {
        "sensor": _create_integration(config, "sensor", "entity"),
        "light": _create_integration(config, "light", "entity"),
        "tag": _create_integration(config, "tag", "entity"),  # excluded
        "mqtt": _create_integration(config, "mqtt", "hub"),
    }

    core_files = _create_core_files_yaml(["sensor", "light", *EXTRA_BASE_PLATFORMS])

    with patch("script.hassfest.core_files.load_yaml_dict", return_value=core_files):
        validate(integrations, config)

    assert not config.errors


def test_missing_entity_platform(config: Config) -> None:
    """Test error when an entity platform is missing from base_platforms."""
    integrations = {
        "sensor": _create_integration(config, "sensor", "entity"),
        "light": _create_integration(config, "light", "entity"),
    }

    # light is missing from base_platforms
    core_files = _create_core_files_yaml(["sensor", *EXTRA_BASE_PLATFORMS])

    with patch("script.hassfest.core_files.load_yaml_dict", return_value=core_files):
        validate(integrations, config)

    assert len(config.errors) == 1
    assert (
        config.errors[0].error
        == "Entity platform 'light' is missing from base_platforms in .core_files.yaml"
    )


def test_unexpected_entry(config: Config) -> None:
    """Test error when base_platforms contains a non-entity-platform entry."""
    integrations = {
        "sensor": _create_integration(config, "sensor", "entity"),
    }

    core_files = _create_core_files_yaml(
        ["sensor", "unknown_thing", *EXTRA_BASE_PLATFORMS]
    )

    with patch("script.hassfest.core_files.load_yaml_dict", return_value=core_files):
        validate(integrations, config)

    assert len(config.errors) == 1
    assert (
        config.errors[0].error
        == "'unknown_thing' in base_platforms in .core_files.yaml is not an entity platform or in EXTRA_BASE_PLATFORMS"
    )

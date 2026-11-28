"""Tests for hassfest core_files validation."""

from pathlib import Path
from unittest.mock import patch

import pytest

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
        == "'unknown_thing' in base_platforms in .core_files.yaml"
        " is not an entity platform or in EXTRA_BASE_PLATFORMS"
    )


def _create_core_integration(
    config: Config, tmp_path: Path, domain: str, code: str
) -> Integration:
    """Create a core integration with the given __init__.py content."""
    integration = _create_integration(config, domain)
    integration.path = tmp_path / domain
    integration.path.mkdir()
    (integration.path / "__init__.py").write_text(code)
    return integration


@pytest.mark.parametrize(
    "code",
    [
        pytest.param('__all__ = ["DOMAIN"]\n', id="assign"),
        pytest.param('__all__: list[str] = ["DOMAIN"]\n', id="annotated_assign"),
    ],
)
def test_core_integration_with_all(config: Config, tmp_path: Path, code: str) -> None:
    """Test no errors when a core integration defines __all__."""
    integrations = {"http": _create_core_integration(config, tmp_path, "http", code)}
    core_files = {
        "base_platforms": [],
        "components": ["homeassistant/components/http/**"],
    }

    with (
        patch("script.hassfest.core_files.load_yaml_dict", return_value=core_files),
        patch("script.hassfest.core_files.EXTRA_BASE_PLATFORMS", set()),
        patch("script.hassfest.core_files.MISSING_ALL", set()),
    ):
        validate(integrations, config)

    assert not config.errors


@pytest.mark.parametrize(
    ("core_files", "extra_base_platforms"),
    [
        pytest.param(
            {"base_platforms": [], "components": ["homeassistant/components/http/**"]},
            set(),
            id="component",
        ),
        pytest.param(
            {"base_platforms": ["homeassistant/components/http/**"]},
            {"http"},
            id="base_platform",
        ),
    ],
)
@pytest.mark.parametrize(
    "code",
    [
        pytest.param('DOMAIN = "http"\n', id="no_all"),
        pytest.param(
            'DOMAIN = "http"\n\ndef func() -> None:\n    __all__ = ["DOMAIN"]\n',
            id="local_all",
        ),
        pytest.param("__all__: list[str]\n", id="annotation_only"),
    ],
)
def test_core_integration_missing_all(
    config: Config,
    tmp_path: Path,
    core_files: dict,
    extra_base_platforms: set[str],
    code: str,
) -> None:
    """Test error when a core integration does not define __all__."""
    domain = "http"
    integrations = {
        domain: _create_core_integration(
            config,
            tmp_path,
            domain,
            code,
        )
    }

    with (
        patch("script.hassfest.core_files.load_yaml_dict", return_value=core_files),
        patch("script.hassfest.core_files.EXTRA_BASE_PLATFORMS", extra_base_platforms),
        patch("script.hassfest.core_files.MISSING_ALL", set()),
    ):
        validate(integrations, config)

    assert [error.error for error in config.errors] == [
        f"Core integration '{domain}' must define `__all__` in its `__init__.py`"
    ]


def test_core_integration_in_missing_all(config: Config, tmp_path: Path) -> None:
    """Test no error when a core integration without __all__ is in MISSING_ALL."""
    integrations = {
        "http": _create_core_integration(config, tmp_path, "http", 'DOMAIN = "http"\n')
    }
    core_files = {
        "base_platforms": [],
        "components": ["homeassistant/components/http/**"],
    }

    with (
        patch("script.hassfest.core_files.load_yaml_dict", return_value=core_files),
        patch("script.hassfest.core_files.EXTRA_BASE_PLATFORMS", set()),
        patch("script.hassfest.core_files.MISSING_ALL", {"http"}),
    ):
        validate(integrations, config)

    assert not config.errors


def test_core_integration_with_all_still_in_missing_all(
    config: Config, tmp_path: Path
) -> None:
    """Test error when a core integration defines __all__ but is in MISSING_ALL."""
    integrations = {
        "http": _create_core_integration(
            config, tmp_path, "http", '__all__ = ["DOMAIN"]\n'
        )
    }
    core_files = {
        "base_platforms": [],
        "components": ["homeassistant/components/http/**"],
    }

    with (
        patch("script.hassfest.core_files.load_yaml_dict", return_value=core_files),
        patch("script.hassfest.core_files.EXTRA_BASE_PLATFORMS", set()),
        patch("script.hassfest.core_files.MISSING_ALL", {"http"}),
    ):
        validate(integrations, config)

    assert [error.error for error in config.errors] == [
        "Core integration 'http' defines `__all__` but is still listed in MISSING_ALL"
    ]

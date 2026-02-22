"""Tests for quality_scale validation."""

from pathlib import Path
from unittest.mock import patch

import pytest

from script.hassfest import quality_scale
from script.hassfest.model import Config

from . import get_integration


@pytest.fixture
def config():
    """Fixture for hassfest Config."""
    return Config(
        root=Path(".").absolute(),
        specific_integrations=None,
        action="validate",
        requirements=True,
    )


def test_validate_no_quality_scale_key(config: Config, mock_core_integration) -> None:
    """Test integration with no quality_scale key in manifest."""
    integration = get_integration("test_integration", config)
    # Ensure quality_scale is None (default in get_integration is just basic manifest)
    assert integration.quality_scale is None

    # Mock that it's not in exemption list
    with patch("script.hassfest.quality_scale.INTEGRATIONS_WITHOUT_SCALE", []):
        quality_scale.validate_iqs_file(config, integration)

    assert len(integration.errors) == 1, integration.errors
    assert "Quality scale definition not found" in integration.errors[0].error


def test_validate_no_quality_scale_key_exempt(
    config: Config, mock_core_integration
) -> None:
    """Test integration with no quality_scale key in manifest."""
    integration = get_integration("test_integration", config)
    # Ensure quality_scale is None (default in get_integration is just basic manifest)
    assert integration.quality_scale is None

    # Mock that it IS in exemption list
    with patch(
        "script.hassfest.quality_scale.INTEGRATIONS_WITHOUT_SCALE",
        ["test_integration"],
    ):
        quality_scale.validate_iqs_file(config, integration)

    assert len(integration.errors) == 0, integration.errors


def test_validate_quality_scale_internal_no_file(
    config: Config, mock_core_integration
) -> None:
    """Test internal integration with no quality_scale file."""
    integration = get_integration("test_integration", config)
    integration._manifest["quality_scale"] = "internal"

    # Mock that file does not exist
    with patch("pathlib.Path.is_file", return_value=False):
        quality_scale.validate_iqs_file(config, integration)

    # Internal integrations don't require a quality scale file, so this should pass.
    assert len(integration.errors) == 0, integration.errors


def test_validate_quality_scale_bronze_no_file(
    config: Config, mock_core_integration
) -> None:
    """Test bronze integration with no quality_scale file."""
    integration = get_integration("test_integration", config)
    integration._manifest["quality_scale"] = "bronze"

    with patch("pathlib.Path.is_file", return_value=False):
        quality_scale.validate_iqs_file(config, integration)

    assert len(integration.errors) == 1, integration.errors
    assert "Quality scale definition YAML not found" in integration.errors[0].error


def test_validate_quality_scale_bronze_no_file_exempt(
    config: Config, mock_core_integration
) -> None:
    """Test bronze integration with no quality_scale file and an exemption."""
    integration = get_integration("test_integration", config)
    integration._manifest["quality_scale"] = "bronze"

    with patch("pathlib.Path.is_file", return_value=False) and patch(
        "script.hassfest.quality_scale.INTEGRATIONS_WITHOUT_QUALITY_SCALE_FILE",
        ["test_integration"],
    ):
        quality_scale.validate_iqs_file(config, integration)

    assert len(integration.errors) == 0, integration.errors


def test_validate_quality_scale_file_present(
    config: Config, mock_core_integration
) -> None:
    """Test integration with quality scale file present."""
    integration = get_integration("test_integration", config)
    integration._manifest["quality_scale"] = "bronze"

    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch(
            "script.hassfest.quality_scale.load_yaml_dict", return_value={"rules": {}}
        ),
        patch("script.hassfest.quality_scale.SCHEMA"),
    ):
        quality_scale.validate_iqs_file(config, integration)

    # Should not have the "not found" error.
    # Might have other errors if rules are missing, but we are testing the file existence check.

    # Check that we didn't get the "Quality scale definition YAML not found" error
    for error in integration.errors:
        assert "Quality scale definition YAML not found" not in error.error, error

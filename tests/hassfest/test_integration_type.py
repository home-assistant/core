"""Tests for hassfest integration_type."""

import pytest

from script.hassfest import integration_type
from script.hassfest.model import Config, Integration

from . import get_integration


def _get_integration(domain: str, config: Config, manifest_extra: dict) -> Integration:
    """Helper to create an integration with extra manifest keys."""
    integration = get_integration(domain, config)
    integration.manifest.update(manifest_extra)
    return integration


@pytest.mark.usefixtures("mock_core_integration")
def test_integration_with_config_flow_and_integration_type(config: Config) -> None:
    """Integration with config_flow and integration_type should pass without errors."""
    integrations = {
        "test": _get_integration(
            "test",
            config,
            {"config_flow": True, "integration_type": "device"},
        )
    }
    integration_type.validate(integrations, config)
    assert integrations["test"].errors == []


@pytest.mark.usefixtures("mock_core_integration")
def test_integration_with_config_flow_missing_integration_type(config: Config) -> None:
    """Integration with config_flow but no integration_type and not in allowlist should error."""
    integrations = {
        "test": _get_integration(
            "test",
            config,
            {"config_flow": True},
        )
    }
    integration_type.validate(integrations, config)
    assert len(integrations["test"].errors) == 1
    assert "missing an `integration_type`" in integrations["test"].errors[0].error


@pytest.mark.usefixtures("mock_core_integration")
def test_integration_with_config_flow_in_allowlist(config: Config) -> None:
    """Integration with config_flow but no integration_type and in allowlist should pass."""
    domain = next(iter(integration_type.MISSING_INTEGRATION_TYPE))
    integrations = {
        domain: _get_integration(
            domain,
            config,
            {"config_flow": True},
        )
    }
    integration_type.validate(integrations, config)
    assert integrations[domain].errors == []


@pytest.mark.usefixtures("mock_core_integration")
def test_integration_with_integration_type_still_in_allowlist(config: Config) -> None:
    """Integration with integration_type but still in allowlist should error."""
    domain = next(iter(integration_type.MISSING_INTEGRATION_TYPE))
    integrations = {
        domain: _get_integration(
            domain,
            config,
            {"config_flow": True, "integration_type": "device"},
        )
    }
    integration_type.validate(integrations, config)
    assert len(integrations[domain].errors) == 1
    assert (
        "still listed in MISSING_INTEGRATION_TYPE"
        in integrations[domain].errors[0].error
    )


@pytest.mark.usefixtures("mock_core_integration")
def test_integration_without_config_flow_skipped(config: Config) -> None:
    """Integration without config_flow should be skipped regardless of integration_type."""
    integrations = {
        "test": _get_integration(
            "test",
            config,
            {},
        )
    }
    integration_type.validate(integrations, config)
    assert integrations["test"].errors == []

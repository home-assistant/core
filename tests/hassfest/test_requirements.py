"""Tests for hassfest requirements."""

from pathlib import Path

import pytest

from script.hassfest.model import Config, Integration
from script.hassfest.requirements import validate_requirements_format


@pytest.fixture
def integration():
    """Fixture for hassfest integration model."""
    return Integration(
        path=Path("homeassistant/components/test").absolute(),
        _config=Config(
            root=Path(".").absolute(),
            specific_integrations=None,
            action="validate",
            requirements=True,
        ),
        _manifest={
            "domain": "test",
            "documentation": "https://example.com",
            "name": "test",
            "codeowners": ["@awesome"],
            "requirements": [],
        },
    )


def test_validate_requirements_format_with_space(integration: Integration) -> None:
    """Test validate requirement with space around separator."""
    integration.manifest["requirements"] = ["test_package == 1"]
    assert not validate_requirements_format(integration)
    assert len(integration.errors) == 1
    assert 'Requirement "test_package == 1" contains a space' in [
        x.error for x in integration.errors
    ]


def test_validate_requirements_format_wrongly_pinned(integration: Integration) -> None:
    """Test requirement with loose pin."""
    integration.manifest["requirements"] = ["test_package>=1"]
    assert not validate_requirements_format(integration)
    assert len(integration.errors) == 1
    assert 'Requirement test_package>=1 need to be pinned "<pkg name>==<version>".' in [
        x.error for x in integration.errors
    ]


def test_validate_requirements_format_ignore_pin_for_custom(
    integration: Integration,
) -> None:
    """Test requirement ignore pinning for custom."""
    integration.manifest["requirements"] = [
        "test_package>=1",
        "test_package",
        "test_package>=1.2.3,<3.2.1",
        "test_package~=0.5.0",
        "test_package>=1.4.2,<1.4.99,>=1.7,<1.8.99",
        "test_package>=1.4.2,<1.9,!=1.5",
        "test_package>=1.4.2;python_version<'3.11'",
    ]
    integration.path = Path("")
    assert validate_requirements_format(integration)
    assert len(integration.errors) == 0


def test_validate_requirements_format_invalid_version(integration: Integration) -> None:
    """Test requirement with invalid version."""
    integration.manifest["requirements"] = ["test_package==invalid"]
    assert not validate_requirements_format(integration)
    assert len(integration.errors) == 1
    assert "Unable to parse package version (invalid) for test_package." in [
        x.error for x in integration.errors
    ]


def test_validate_requirements_format_successful(integration: Integration) -> None:
    """Test requirement with successful result."""
    integration.manifest["requirements"] = [
        "test_package==1.2.3",
        "test_package[async]==1.2.3",
        "test_package[async,encrypted]==1.2.3",
    ]
    assert validate_requirements_format(integration)
    assert len(integration.errors) == 0


def test_validate_requirements_format_github_core(integration: Integration) -> None:
    """Test requirement that points to github fails with core component."""
    integration.manifest["requirements"] = [
        "git+https://github.com/user/project.git@1.2.3",
    ]
    assert not validate_requirements_format(integration)
    assert len(integration.errors) == 1


def test_validate_requirements_format_github_custom(integration: Integration) -> None:
    """Test requirement that points to github succeeds with custom component."""
    integration.manifest["requirements"] = [
        "git+https://github.com/user/project.git@1.2.3",
    ]
    integration.path = Path("")
    assert validate_requirements_format(integration)
    assert len(integration.errors) == 0

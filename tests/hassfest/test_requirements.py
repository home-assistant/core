"""Tests for hassfest requirements."""

from collections.abc import Generator
from importlib.metadata import PackagePath
from pathlib import Path
from unittest.mock import patch

import pytest

from script.hassfest.model import Config, Integration
from script.hassfest.requirements import (
    FORBIDDEN_PACKAGE_NAMES,
    PACKAGE_CHECK_PREPARE_UPDATE,
    PACKAGE_CHECK_VERSION_RANGE,
    _packages_checked_files_cache,
    check_dependency_files,
    check_dependency_version_range,
    validate_requirements_format,
)


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


@pytest.fixture
def mock_forbidden_package_names() -> Generator[None]:
    """Fixture for FORBIDDEN_PACKAGE_NAMES."""
    # pylint: disable-next=global-statement
    global FORBIDDEN_PACKAGE_NAMES  # noqa: PLW0603
    original = FORBIDDEN_PACKAGE_NAMES.copy()
    FORBIDDEN_PACKAGE_NAMES = {"test", "tests"}
    try:
        yield
    finally:
        FORBIDDEN_PACKAGE_NAMES = original


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


@pytest.mark.parametrize(
    ("version", "result"),
    [
        (">2", True),
        (">=2.0", True),
        (">=2.0,<4", True),
        ("<4", True),
        ("<=3.0", True),
        (">=2.0,<4;python_version<'3.14'", True),
        ("<3", False),
        ("==2.*", False),
        ("~=2.0", False),
        ("<=2.100", False),
        (">2,<3", False),
        (">=2.0,<3", False),
        (">=2.0,<3;python_version<'3.14'", False),
    ],
)
def test_dependency_version_range_prepare_update(
    version: str, result: bool, integration: Integration
) -> None:
    """Test dependency version range check for prepare update is working correctly."""
    with (
        patch.dict(PACKAGE_CHECK_VERSION_RANGE, {"numpy-test": "SemVer"}, clear=True),
        patch.dict(PACKAGE_CHECK_PREPARE_UPDATE, {"numpy-test": 3}, clear=True),
    ):
        assert (
            check_dependency_version_range(
                integration,
                "test",
                pkg="numpy-test",
                version=version,
                package_exceptions=set(),
            )
            == result
        )


@pytest.mark.usefixtures("mock_forbidden_package_names")
def test_check_dependency_package_names(integration: Integration) -> None:
    """Test dependency package names check for forbidden package names is working correctly."""
    package = "homeassistant"
    pkg = "my_package"

    # Forbidden top level directories: test, tests
    pkg_files = [
        PackagePath("my_package/__init__.py"),
        PackagePath("my_package-1.0.0.dist-info/METADATA"),
        PackagePath("tests/test_some_function.py"),
        PackagePath("test/submodule/test_some_other_function.py"),
    ]
    with (
        patch(
            "script.hassfest.requirements.files", return_value=pkg_files
        ) as mock_files,
        patch.dict(_packages_checked_files_cache, {}, clear=True),
    ):
        assert not _packages_checked_files_cache
        assert check_dependency_files(integration, package, pkg, ()) is False
        assert _packages_checked_files_cache[pkg]["top_level"] == {"tests", "test"}
        assert len(integration.errors) == 2
        assert (
            f"Package {pkg} has a forbidden top level directory 'tests' in {package}"
            in [x.error for x in integration.errors]
        )
        assert (
            f"Package {pkg} has a forbidden top level directory 'test' in {package}"
            in [x.error for x in integration.errors]
        )
        integration.errors.clear()

        # Repeated call should use cache
        assert check_dependency_files(integration, package, pkg, ()) is False
        assert mock_files.call_count == 1
        assert len(integration.errors) == 2
        integration.errors.clear()

    # Exceptions set
    pkg_files = [
        PackagePath("my_package/__init__.py"),
        PackagePath("my_package.dist-info/METADATA"),
        PackagePath("tests/test_some_function.py"),
    ]
    with (
        patch(
            "script.hassfest.requirements.files", return_value=pkg_files
        ) as mock_files,
        patch.dict(_packages_checked_files_cache, {}, clear=True),
    ):
        assert not _packages_checked_files_cache
        assert (
            check_dependency_files(integration, package, pkg, package_exceptions={pkg})
            is False
        )
        assert _packages_checked_files_cache[pkg]["top_level"] == {"tests"}
        assert len(integration.errors) == 0
        assert len(integration.warnings) == 1
        assert (
            f"Package {pkg} has a forbidden top level directory 'tests' in {package}"
            in [x.error for x in integration.warnings]
        )
        integration.warnings.clear()

        # Repeated call should use cache
        assert (
            check_dependency_files(integration, package, pkg, package_exceptions={pkg})
            is False
        )
        assert mock_files.call_count == 1
        assert len(integration.errors) == 0
        assert len(integration.warnings) == 1
        integration.warnings.clear()

    # All good
    pkg_files = [
        PackagePath("my_package/__init__.py"),
        PackagePath("my_package.dist-info/METADATA"),
    ]
    with (
        patch(
            "script.hassfest.requirements.files", return_value=pkg_files
        ) as mock_files,
        patch.dict(_packages_checked_files_cache, {}, clear=True),
    ):
        assert not _packages_checked_files_cache
        assert check_dependency_files(integration, package, pkg, ()) is True
        assert _packages_checked_files_cache[pkg]["top_level"] == set()
        assert len(integration.errors) == 0

        # Repeated call should use cache
        assert check_dependency_files(integration, package, pkg, ()) is True
        assert mock_files.call_count == 1
        assert len(integration.errors) == 0


def test_check_dependency_file_names(integration: Integration) -> None:
    """Test dependency file name check for forbidden files is working correctly."""
    package = "homeassistant"
    pkg = "my_package"

    # Forbidden file: 'py.typed' at top level
    pkg_files = [
        PackagePath("py.typed"),
        PackagePath("my_package.py"),
        PackagePath("my_package-1.0.0.dist-info/METADATA"),
    ]
    with (
        patch(
            "script.hassfest.requirements.files", return_value=pkg_files
        ) as mock_files,
        patch.dict(_packages_checked_files_cache, {}, clear=True),
    ):
        assert not _packages_checked_files_cache
        assert check_dependency_files(integration, package, pkg, ()) is False
        assert _packages_checked_files_cache[pkg]["file_names"] == {"py.typed"}
        assert len(integration.errors) == 1
        assert f"Package {pkg} has a forbidden file 'py.typed' in {package}" in [
            x.error for x in integration.errors
        ]
        integration.errors.clear()

        # Repeated call should use cache
        assert check_dependency_files(integration, package, pkg, ()) is False
        assert mock_files.call_count == 1
        assert len(integration.errors) == 1
        integration.errors.clear()

    # All good
    pkg_files = [
        PackagePath("my_package/__init__.py"),
        PackagePath("my_package/py.typed"),
        PackagePath("my_package.dist-info/METADATA"),
    ]
    with (
        patch(
            "script.hassfest.requirements.files", return_value=pkg_files
        ) as mock_files,
        patch.dict(_packages_checked_files_cache, {}, clear=True),
    ):
        assert not _packages_checked_files_cache
        assert check_dependency_files(integration, package, pkg, ()) is True
        assert _packages_checked_files_cache[pkg]["file_names"] == set()
        assert len(integration.errors) == 0

        # Repeated call should use cache
        assert check_dependency_files(integration, package, pkg, ()) is True
        assert mock_files.call_count == 1
        assert len(integration.errors) == 0

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
    _load_requirement_file,
    _packages_checked_files_cache,
    check_dependency_files,
    check_dependency_version_range,
    validate_custom_requirements,
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
    """Test dependency package names check for forbidden names."""
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
        PackagePath("some_script.Pth"),
        PackagePath("entry_point.start"),
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
        assert _packages_checked_files_cache[pkg]["file_names"] == {
            "py.typed",
            "some_script.Pth",
            "entry_point.start",
        }
        assert len(integration.errors) == 3
        assert f"Package {pkg} has a forbidden file 'py.typed' in {package}" in [
            x.error for x in integration.errors
        ]
        assert f"Package {pkg} has a forbidden file 'some_script.Pth' in {package}" in [
            x.error for x in integration.errors
        ]
        assert (
            f"Package {pkg} has a forbidden file 'entry_point.start' in {package}"
            in [x.error for x in integration.errors]
        )
        integration.errors.clear()

        # Repeated call should use cache
        assert check_dependency_files(integration, package, pkg, ()) is False
        assert mock_files.call_count == 1
        assert len(integration.errors) == 3
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


@pytest.fixture
def core_config(tmp_path: Path) -> Generator[Config]:
    """Fixture for a Config pointing at a stubbed Home Assistant checkout."""
    (tmp_path / "homeassistant").mkdir()
    (tmp_path / "requirements.txt").write_text(
        "# Home Assistant Core\n"
        "-c homeassistant/package_constraints.txt\n"
        "aiohttp==3.14.3\n"
    )
    (tmp_path / "requirements_all.txt").write_text(
        "-r requirements.txt\n\n# homeassistant.components.modbus\npymodbus==3.13.1\n"
    )
    (tmp_path / "homeassistant" / "package_constraints.txt").write_text(
        "pymodbus==3.13.1\n"
        "aiofiles>=24.1.0\n"
        "poetry==1000000000.0.0\n"
        "tenacity!=8.4.0\n"
        "auth0-python<5.0\n"
        # Listed twice, as package_constraints.txt does for some packages
        "dupe-package<2.0\n"
        "dupe-package>=1.5\n"
    )

    _load_requirement_file.cache_clear()
    yield Config(
        root=tmp_path,
        specific_integrations=None,
        action="validate",
        requirements=False,
    )
    _load_requirement_file.cache_clear()


@pytest.fixture
def custom_integration(core_config: Config) -> Integration:
    """Fixture for a custom integration validated against a stubbed core."""
    return Integration(
        path=Path("custom_components/test").absolute(),
        _config=core_config,
        _manifest={
            "domain": "test",
            "documentation": "https://example.com",
            "name": "test",
            "codeowners": ["@awesome"],
            "requirements": [],
        },
    )


@pytest.mark.parametrize(
    ("requirement", "error"),
    [
        pytest.param(
            "aiohttp==3.14.3",
            "Requirement aiohttp==3.14.3 is a dependency of Home Assistant itself "
            "and must not be listed in the manifest of a custom integration.",
            id="core_dependency",
        ),
        pytest.param(
            "pymodbus==3.6.2",
            "Requirement pymodbus==3.6.2 is incompatible with pymodbus==3.13.1, "
            "which Home Assistant depends on.",
            id="pinned_below_core",
        ),
        pytest.param(
            "pymodbus>=3.20.0",
            "Requirement pymodbus>=3.20.0 is incompatible with pymodbus==3.13.1, "
            "which Home Assistant depends on.",
            id="minimum_above_core",
        ),
        pytest.param(
            "pymodbus==3.13.1",
            "Requirement pymodbus==3.13.1 pins a package Home Assistant depends on "
            '(pymodbus==3.13.1). Use a minimum version ("pymodbus>=3.13.1") instead, '
            "so it can follow along when Home Assistant updates it.",
            id="pinned_to_core_version",
        ),
        pytest.param(
            "aiofiles<24.0.0",
            "Requirement aiofiles<24.0.0 is incompatible with aiofiles>=24.1.0, "
            "which Home Assistant's package constraints require.",
            id="violates_package_constraint",
        ),
        pytest.param(
            "poetry>=1",
            "Requirement poetry>=1 is prohibited by Home Assistant, poetry must "
            "not be installed.",
            id="prohibited_package",
        ),
        pytest.param(
            "pymodbus==3.6.2;platform_machine=='aarch64'",
            "Requirement pymodbus==3.6.2;platform_machine=='aarch64' is "
            "incompatible with pymodbus==3.13.1, which Home Assistant depends on.",
            id="marker_applying_on_another_platform",
        ),
        pytest.param(
            "tenacity==8.4.0",
            "Requirement tenacity==8.4.0 is incompatible with tenacity!=8.4.0, "
            "which Home Assistant's package constraints require.",
            id="violates_excluded_version",
        ),
        pytest.param(
            "dupe-package==3.0",
            "Requirement dupe-package==3.0 is incompatible with "
            "dupe-package<2.0,>=1.5, which Home Assistant's package constraints "
            "require.",
            id="violates_merged_constraints",
        ),
    ],
)
def test_validate_custom_requirements_invalid(
    custom_integration: Integration,
    core_config: Config,
    requirement: str,
    error: str,
) -> None:
    """Test custom integration requirements that clash with Home Assistant."""
    custom_integration.manifest["requirements"] = [requirement]

    assert not validate_custom_requirements(custom_integration, core_config)
    assert [x.error for x in custom_integration.errors] == [error]


@pytest.mark.parametrize(
    "requirement",
    [
        pytest.param("pymodbus>=3.10.0", id="minimum_below_core"),
        pytest.param("pymodbus>=3.13.1", id="minimum_equal_to_core"),
        pytest.param("aiofiles>=25.0.0", id="within_package_constraint"),
        pytest.param("unknown-package==1.2.3", id="unknown_package"),
        pytest.param("pymodbus==3.6.2;python_version<'3.0'", id="marker_not_applying"),
        pytest.param("aiofiles>25,<25.0.1", id="range_excluding_own_boundaries"),
        pytest.param("pymodbus>3.13.0,<4", id="range_around_core_version"),
        pytest.param("pymodbus==3.13.*", id="wildcard_matching_core_version"),
        pytest.param("pymodbus~=3.13.1", id="compatible_release"),
        pytest.param("tenacity>8.4.0,<9", id="range_around_excluded_version"),
        pytest.param("auth0-python==4.9.0", id="pinned_package_we_only_constrain"),
        pytest.param("dupe-package==1.7", id="within_merged_constraints"),
        pytest.param("git+https://github.com/user/project.git@1.2.3", id="git_url"),
    ],
)
def test_validate_custom_requirements_valid(
    custom_integration: Integration, core_config: Config, requirement: str
) -> None:
    """Test custom integration requirements that Home Assistant is fine with."""
    custom_integration.manifest["requirements"] = [requirement]

    assert validate_custom_requirements(custom_integration, core_config)
    assert not custom_integration.errors


def test_validate_custom_requirements_skips_core(
    custom_integration: Integration, core_config: Config
) -> None:
    """Test core integrations are exempt, they are what we validate against."""
    custom_integration.path = core_config.root / "homeassistant/components/modbus"
    custom_integration.manifest["requirements"] = ["pymodbus==3.13.1"]

    assert validate_custom_requirements(custom_integration, core_config)
    assert not custom_integration.errors

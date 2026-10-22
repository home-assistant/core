"""Tests for the gen_requirements_all script."""

from pathlib import Path
import tomllib
from unittest.mock import patch

import pytest

from script import gen_requirements_all
from script.hassfest.requirements_util import _normalize_package_name


def test_pytest_package_dependency_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sync base and optional pins without changing publish metadata or extras."""
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\ndependencies = ["core-lib==2.0.0"]\n')
    Path("requirements_test.txt").write_text(
        "# Test dependencies\n-c constraints.txt\n\ntest_lib==3.0.0\n"
    )
    package = gen_requirements_all.PYTEST_PACKAGE_PATH
    package.parent.mkdir(parents=True)
    package.write_text(
        """[project]
version = "0.0.0"
dependencies = ["homeassistant", "core-lib==1.0.0", "test-lib==1.0.0"]

[project.optional-dependencies]
radio = ["radio-lib[scan]==1.0.0; sys_platform == 'linux'"]

[project.entry-points.pytest11]
pytest_homeassistant = "pytest_homeassistant.bootstrap"
"""
    )
    output = gen_requirements_all.pytest_package_output(
        {"radio-lib[other]==4.0.0": ["homeassistant.components.radio"]}
    )
    project = tomllib.loads(output)["project"]
    assert project["version"] == "0.0.0"
    assert project["dependencies"] == [
        "homeassistant",
        "core-lib==2.0.0",
        "test-lib==3.0.0",
    ]
    assert project["optional-dependencies"] == {
        "radio": ['radio-lib[scan]==4.0.0; sys_platform == "linux"']
    }
    assert project["entry-points"] == {
        "pytest11": {"pytest_homeassistant": "pytest_homeassistant.bootstrap"}
    }


def test_overrides_normalized() -> None:
    """Test override lists are using normalized package names."""
    for req in gen_requirements_all.EXCLUDED_REQUIREMENTS_ALL:
        assert req == _normalize_package_name(req)
    for req in gen_requirements_all.INCLUDED_REQUIREMENTS_WHEELS:
        assert req == _normalize_package_name(req)
    for overrides in gen_requirements_all.OVERRIDDEN_REQUIREMENTS_ACTIONS.values():
        for req in overrides["exclude"]:
            assert req == _normalize_package_name(req)
        for req in overrides["include"]:
            assert req == _normalize_package_name(req)


def test_include_overrides_subsets() -> None:
    """Test packages in include override lists are present in the exclude list."""
    for req in gen_requirements_all.INCLUDED_REQUIREMENTS_WHEELS:
        assert req in gen_requirements_all.EXCLUDED_REQUIREMENTS_ALL
    for overrides in gen_requirements_all.OVERRIDDEN_REQUIREMENTS_ACTIONS.values():
        for req in overrides["include"]:
            assert req in gen_requirements_all.EXCLUDED_REQUIREMENTS_ALL


def test_requirement_override_markers() -> None:
    """Test override markers are applied to the correct requirements."""
    data = {
        "pytest": {
            "exclude": set(),
            "include": set(),
            "markers": {"env-canada": "python_version<'3.13'"},
        }
    }
    with patch.dict(
        gen_requirements_all.OVERRIDDEN_REQUIREMENTS_ACTIONS, data, clear=True
    ):
        assert (
            gen_requirements_all.process_action_requirement(
                "env-canada==0.8.0", "pytest"
            )
            == "env-canada==0.8.0;python_version<'3.13'"
        )
        assert (
            gen_requirements_all.process_action_requirement("other==1.0", "pytest")
            == "other==1.0"
        )


def test_merge_requirement_extras() -> None:
    """Test requirements that only differ in extras are merged."""
    reqs = {
        "lorawan-connection[chirpstack]==1.0.0": ["homeassistant.components.a"],
        "lorawan-connection==1.0.0": ["homeassistant.components.b"],
        "lorawan_connection[ttn]==1.0.0": ["homeassistant.components.c"],
        "other[b,a]==2.0.0": ["homeassistant.components.a"],
    }
    errors: list[str] = []
    assert gen_requirements_all.merge_requirement_extras(errors, reqs) == {
        "lorawan-connection[chirpstack,ttn]==1.0.0": [
            "homeassistant.components.a",
            "homeassistant.components.b",
            "homeassistant.components.c",
        ],
        # Requirements without a merge keep their original form
        "other[b,a]==2.0.0": ["homeassistant.components.a"],
    }
    assert errors == []


@pytest.mark.parametrize(
    "conflicting_req",
    [
        pytest.param("pinned==2.0.0", id="version"),
        pytest.param("pinned[extra]==2.0.0", id="version_with_extra"),
        pytest.param("pinned==1.0.0;sys_platform=='linux'", id="marker"),
    ],
)
def test_merge_requirement_extras_conflict(conflicting_req: str) -> None:
    """Test requirements of one package with different versions or markers fail."""
    reqs = {
        "pinned==1.0.0": ["homeassistant.components.a"],
        conflicting_req: ["homeassistant.components.b"],
        "other==1.0.0": ["homeassistant.components.c"],
    }
    errors: list[str] = []
    assert gen_requirements_all.merge_requirement_extras(errors, reqs) == {
        "other==1.0.0": ["homeassistant.components.c"],
    }
    assert errors == [
        "pinned[Conflicting requirements: "
        "pinned==1.0.0 (homeassistant.components.a), "
        f"{conflicting_req} (homeassistant.components.b)]"
    ]

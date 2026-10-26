"""Tests for the ha-deprecation-cleanup skill's find_due_deprecations script."""

import importlib.util
import json
from pathlib import Path
import sys
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from syrupy.assertion import SnapshotAssertion

SCRIPT = (
    Path(__file__).parents[2]
    / ".claude/skills/ha-deprecation-cleanup/scripts/find_due_deprecations.py"
)
_spec = importlib.util.spec_from_file_location("find_due_deprecations", SCRIPT)
if TYPE_CHECKING:
    assert _spec is not None
    assert _spec.loader is not None
find = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(find)

FILES = {
    "homeassistant/const.py": """
        MAJOR_VERSION: Final = 2026
        MINOR_VERSION: Final = 11

        _DEPRECATED_DUE = DeprecatedConstant("old", "new", "2026.10")
        _DEPRECATED_LATER = DeprecatedConstant("old", "new", "2027.1")
        _DEPRECATED_ENUM = DeprecatedConstantEnum(SomeEnum.OLD, "2025.6")
        _DEPRECATED_NONE = DeprecatedAlias(Old, "new.Old", None)
    """,
    "homeassistant/helpers/frame.py": """
        def report_usage(what, *, breaks_in_ha_version=None):
            _report(what, breaks_in_ha_version=breaks_in_ha_version)
    """,
    "homeassistant/helpers/device_registry.py": """
        def async_get_or_create():
            report_usage("old", breaks_in_ha_version="2025.12.0")
    """,
    "homeassistant/components/alpha/const.py": """
        BREAKS_IN: Final = "2026.11.0"
        LATER = "2026.12.0"
    """,
    "homeassistant/components/alpha/__init__.py": """
        from .const import BREAKS_IN, LATER

        async def async_setup(hass):
            async_create_issue(hass, "alpha", "yaml", breaks_in_ha_version="2026.9.0")
            async_create_issue(hass, "alpha", "later", breaks_in_ha_version=LATER)
            async_create_issue(hass, "alpha", "const", breaks_in_ha_version=BREAKS_IN)
            data = {"breaks_in_ha_version": "2025.1"}
            async_create_issue(hass, "alpha", "none", breaks_in_ha_version=None)
    """,
    "homeassistant/components/beta/util.py": """
        OLD = "2025.6.0"

        def deprecate_entity(hass, unique_id, version: str = "2026.9.0"):
            async_create_issue(hass, "beta", unique_id, breaks_in_ha_version=version)
    """,
    "homeassistant/components/beta/sensor.py": """
        from .util import OLD, deprecate_entity

        def setup(hass):
            deprecate_entity(hass, "default")
            deprecate_entity(hass, "positional", "2026.12.0")
            deprecate_entity(hass, "keyword", version=OLD)
    """,
    "homeassistant/components/gamma/entity.py": """
        class Entity:
            def _create_issue(self, version):
                async_create_issue(breaks_in_ha_version=version)

            def _deprecate(self):
                self._create_issue("2026.1.0")

            def report(self):
                async_create_issue(breaks_in_ha_version=self.breaks_in)
                async_create_issue(breaks_in_ha_version=UNKNOWN_VERSION)
    """,
    "homeassistant/components/delta/helpers.py": """
        def create_issue(hass, version):
            async_create_issue(hass, breaks_in_ha_version=version)

        def setup(hass, **kwargs):
            create_issue(hass, "2025.1.0")
            create_issue(hass, **kwargs)
    """,
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a fake core checkout with deprecations of every supported kind."""
    for name, content in FILES.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(content).lstrip())
    return tmp_path


def test_scan(repo: Path, snapshot: SnapshotAssertion) -> None:
    """Test the groups, unresolved and passthrough items found in the fake repo."""
    assert find.scan(repo, find.dev_version(repo)) == snapshot


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        pytest.param((2025, 1), ["alpha"], id="only-the-oldest"),
        pytest.param(
            (2027, 1),
            [
                "const.py",
                "helpers/device_registry.py",
                "alpha",
                "beta",
                "gamma",
            ],
            id="everything-resolvable",
        ),
    ],
)
def test_scan_due_rule(
    repo: Path, current: tuple[int, int], expected: list[str]
) -> None:
    """Test deprecations are due at or below the current version."""
    groups = [group["name"] for group in find.scan(repo, current)["groups"]]
    assert sorted(groups) == sorted(expected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("2026.9", (2026, 9), id="minor"),
        pytest.param("2026.11.0", (2026, 11), id="patch"),
        pytest.param("2026.1.0b0", None, id="beta"),
        pytest.param("version", None, id="not-a-version"),
    ],
)
def test_parse_version(value: str, expected: tuple[int, int] | None) -> None:
    """Test parsing a breaks_in_ha_version value."""
    assert find.parse_version(value) == expected


@pytest.mark.parametrize(
    ("name", "version", "expected"),
    [
        pytest.param(
            "tplink", "2025.4", "deprecation-cleanup/tplink-2025.4", id="integration"
        ),
        pytest.param(
            "helpers/device_registry.py",
            "2025.12",
            "deprecation-cleanup/helpers-device_registry-2025.12",
            id="core-module",
        ),
        pytest.param(
            "const.py",
            "2026.10",
            "deprecation-cleanup/const-2026.10",
            id="top-level-module",
        ),
    ],
)
def test_branch_name(name: str, version: str, expected: str) -> None:
    """Test cleanup branch names."""
    assert find.branch_name(name, version) == expected


@pytest.mark.parametrize(
    ("argv", "expected_version"),
    [
        pytest.param([], "2026.11", id="dev-version"),
        pytest.param(["--version", "2027.1"], "2027.1", id="version-option"),
    ],
)
def test_main(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    expected_version: str,
) -> None:
    """Test the command line prints the scan as JSON."""
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["find_due_deprecations.py", *argv])
    find.main()
    assert json.loads(capsys.readouterr().out)["current_version"] == expected_version


def test_main_not_in_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the command line exits when not run from the repository root."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["find_due_deprecations.py"])
    with pytest.raises(
        SystemExit, match="Run this from the root of a home-assistant/core checkout"
    ):
        find.main()


def test_main_invalid_version(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the command line exits on an invalid --version."""
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["find_due_deprecations.py", "--version", "next"])
    with pytest.raises(SystemExit, match="Invalid version: next"):
        find.main()

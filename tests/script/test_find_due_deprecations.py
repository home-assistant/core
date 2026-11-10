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


# Three files using a VERSION constant that two of them define differently.
SAME_NAME_FILES = {
    "homeassistant/components/epsilon/a.py": """
        VERSION = "2025.1.0"

        async_create_issue(breaks_in_ha_version=VERSION)
    """,
    "homeassistant/components/epsilon/b.py": """
        VERSION = "2099.1.0"

        async_create_issue(breaks_in_ha_version=VERSION)

        def make_issue(version=VERSION):
            async_create_issue(breaks_in_ha_version=version)
    """,
    "homeassistant/components/epsilon/c.py": """
        from .b import make_issue

        async_create_issue(breaks_in_ha_version=VERSION)
        make_issue()
    """,
}

# Two classes with a create_issue() method of the same name but other defaults.
SAME_FUNCTION_NAME_FILES = {
    "homeassistant/components/zeta/entity.py": """
        class Old:
            def create_issue(self, version="2026.9.0"):
                async_create_issue(breaks_in_ha_version=version)

            def setup(self):
                self.create_issue()

        class New:
            def create_issue(self, version="2099.1.0"):
                async_create_issue(breaks_in_ha_version=version)

            def setup(self):
                self.create_issue()
    """,
}

# Several deprecations in one integration that all break in 2026.1.
SAME_VERSION_FILES = {
    "homeassistant/components/eta/__init__.py": """
        DOMAIN = "eta"

        def setup(hass, entry):
            async_create_issue(
                hass, DOMAIN, "deprecated_yaml", breaks_in_ha_version="2026.1.0"
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_option_{entry.entry_id}",
                breaks_in_ha_version="2026.1.0",
            )
            issue_registry.async_get_or_create(
                DOMAIN,
                issue_id=f"{DOMAIN}_deprecated_service",
                breaks_in_ha_version="2026.1",
            )
            report_usage("uses an old API", breaks_in_ha_version="2026.1.0")
    """,
}


def write_repo(root: Path, files: dict[str, str]) -> Path:
    """Write a fake core checkout."""
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(content).lstrip())
    return root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a fake core checkout with deprecations of every supported kind."""
    return write_repo(tmp_path, FILES)


def test_scan(repo: Path, snapshot: SnapshotAssertion) -> None:
    """Test the deprecations, unresolved and passthrough items in the fake repo."""
    assert find.scan(repo, find.dev_version(repo)) == snapshot


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        pytest.param(
            (2025, 1),
            ["deprecation-cleanup/alpha-2025.1"],
            id="only-the-oldest",
        ),
        pytest.param(
            (2027, 1),
            [
                "deprecation-cleanup/alpha-2025.1",
                "deprecation-cleanup/alpha-2026.9-yaml",
                "deprecation-cleanup/alpha-2026.11-const",
                "deprecation-cleanup/alpha-2026.12-later",
                "deprecation-cleanup/beta-2025.6-keyword",
                "deprecation-cleanup/beta-2026.9-default",
                "deprecation-cleanup/beta-2026.12-positional",
                "deprecation-cleanup/const-2025.6",
                "deprecation-cleanup/const-2026.10",
                "deprecation-cleanup/const-2027.1",
                "deprecation-cleanup/gamma-2026.1",
                "deprecation-cleanup/helpers-device_registry-2025.12",
            ],
            id="everything-resolvable",
        ),
    ],
)
def test_scan_due_rule(
    repo: Path, current: tuple[int, int], expected: list[str]
) -> None:
    """Test the deprecations due at or below the current version."""
    assert [
        deprecation["branch"]
        for deprecation in find.scan(repo, current)["deprecations"]
    ] == expected


def test_scan_same_version(tmp_path: Path) -> None:
    """Test each repair issue of a version is its own deprecation and branch."""
    result = find.scan(write_repo(tmp_path, SAME_VERSION_FILES), (2026, 1))
    assert [
        (deprecation["branch"], deprecation["issue_id"])
        for deprecation in result["deprecations"]
    ] == [
        ("deprecation-cleanup/eta-2026.1", None),
        ("deprecation-cleanup/eta-2026.1-deprecated_option", "deprecated_option"),
        ("deprecation-cleanup/eta-2026.1-deprecated_yaml", "deprecated_yaml"),
        (
            "deprecation-cleanup/eta-2026.1-eta_deprecated_service",
            "eta_deprecated_service",
        ),
    ]


def test_scan_branch_name_after_sibling_removed(tmp_path: Path) -> None:
    """Test a deprecation keeps its branch name when another one is removed."""
    write_repo(
        tmp_path,
        {
            "homeassistant/components/eta/__init__.py": """
                def setup(hass, entry):
                    ir.async_create_issue(
                        hass,
                        "eta",
                        f"deprecated_option_{entry.entry_id}",
                        breaks_in_ha_version="2026.1.0",
                    )
            """,
        },
    )
    result = find.scan(tmp_path, (2026, 1))
    assert [deprecation["branch"] for deprecation in result["deprecations"]] == [
        "deprecation-cleanup/eta-2026.1-deprecated_option"
    ]


@pytest.mark.parametrize(
    "helper",
    [
        pytest.param(
            """
            def deprecate(hass, issue_id, version="2026.1.0"):
                async_create_issue(
                    hass, "theta", issue_id, breaks_in_ha_version=version
                )
            """,
            id="forwarded-version",
        ),
        pytest.param(
            """
            def deprecate(hass, issue_id):
                async_create_issue(
                    hass, "theta", issue_id, breaks_in_ha_version="2026.1.0"
                )
            """,
            id="literal-version",
        ),
        pytest.param(
            """
            REMOVAL_VERSION = "2026.1.0"

            def deprecate(hass, issue_id):
                async_create_issue(
                    hass, "theta", issue_id, breaks_in_ha_version=REMOVAL_VERSION
                )
            """,
            id="constant-version",
        ),
    ],
)
def test_scan_forwarded_issue_id(tmp_path: Path, helper: str) -> None:
    """Test issue ids passed through a helper split the deprecations."""
    write_repo(
        tmp_path,
        {
            "homeassistant/components/theta/util.py": helper,
            "homeassistant/components/theta/sensor.py": """
                def setup(hass, entry):
                    deprecate(hass, "deprecated_yaml")
                    deprecate(hass, f"deprecated_sensor_{entry.entry_id}")
            """,
        },
    )
    result = find.scan(tmp_path, (2026, 1))
    assert [deprecation["branch"] for deprecation in result["deprecations"]] == [
        "deprecation-cleanup/theta-2026.1-deprecated_sensor",
        "deprecation-cleanup/theta-2026.1-deprecated_yaml",
    ]


def test_scan_issue_id_with_unpacked_kwargs(tmp_path: Path) -> None:
    """Test a positional issue id is found when the call also unpacks kwargs."""
    write_repo(
        tmp_path,
        {
            "homeassistant/components/kappa/__init__.py": """
                def setup(hass, options):
                    async_create_issue(
                        hass,
                        "kappa",
                        "deprecated_yaml",
                        breaks_in_ha_version="2026.1",
                        **options,
                    )
                    async_create_issue(
                        hass,
                        "kappa",
                        "deprecated_service",
                        breaks_in_ha_version="2026.1",
                        **options,
                    )
            """,
        },
    )
    result = find.scan(tmp_path, (2026, 1))
    assert [deprecation["branch"] for deprecation in result["deprecations"]] == [
        "deprecation-cleanup/kappa-2026.1-deprecated_service",
        "deprecation-cleanup/kappa-2026.1-deprecated_yaml",
    ]


def test_scan_generic_entity_descriptor(tmp_path: Path) -> None:
    """Test the version passed to a subscripted deprecation class is found."""
    write_repo(
        tmp_path,
        {
            "homeassistant/components/iota/entity.py": """
                class IotaEntity:
                    unit: Final = DeprecatedEntityProperty[str]("native_unit", "2026.1")
                    _attr_unit: Final = DeprecatedEntityAttr[str](
                        "_attr_native_unit", "2026.1"
                    )
            """,
        },
    )
    result = find.scan(tmp_path, (2026, 1))
    assert [
        (deprecation["branch"], [item["line"] for item in deprecation["items"]])
        for deprecation in result["deprecations"]
    ] == [("deprecation-cleanup/iota-2026.1", [2, 4])]


def test_scan_enum_with_deprecated_members(tmp_path: Path) -> None:
    """Test the versions of deprecated enum members are found."""
    write_repo(
        tmp_path,
        {
            "homeassistant/components/kappa/const.py": """
                class KappaState(
                    StrEnum,
                    metaclass=EnumWithDeprecatedMembers,
                    deprecated={
                        "STANDBY": ("KappaState.OFF", "2026.1.0"),
                        "PAUSED": ("KappaState.IDLE", "2099.1.0"),
                    },
                ):
                    OFF = "off"

                class Other(Base, deprecated={"OLD": ("NEW", "2026.1.0")}):
                    OLD = "old"
            """,
        },
    )
    result = find.scan(tmp_path, (2026, 1))
    assert [
        (deprecation["branch"], [item["line"] for item in deprecation["items"]])
        for deprecation in result["deprecations"]
    ] == [("deprecation-cleanup/kappa-2026.1", [5])]


def test_scan_same_constant_name(tmp_path: Path) -> None:
    """Test constants with the same name in several files are not mixed up."""
    result = find.scan(write_repo(tmp_path, SAME_NAME_FILES), (2099, 1))
    # Each file uses its own VERSION, and the default is resolved where it is
    # defined, not where make_issue() is called.
    assert [
        (
            deprecation["branch"],
            [(item["file"], item["line"]) for item in deprecation["items"]],
        )
        for deprecation in result["deprecations"]
    ] == [
        (
            "deprecation-cleanup/epsilon-2025.1",
            [("homeassistant/components/epsilon/a.py", 3)],
        ),
        (
            "deprecation-cleanup/epsilon-2099.1",
            [
                ("homeassistant/components/epsilon/b.py", 3),
                ("homeassistant/components/epsilon/c.py", 4),
            ],
        ),
    ]
    # c.py doesn't define VERSION and the integration has two values for it.
    assert [(item["file"], item["source"]) for item in result["unresolved"]] == [
        ("homeassistant/components/epsilon/c.py", "VERSION")
    ]


def test_scan_positional_only_receiver(tmp_path: Path) -> None:
    """Test a method with a positional-only self gets its callers' versions."""
    write_repo(
        tmp_path,
        {
            "homeassistant/components/lambda_/entity.py": """
                class Entity:
                    def create_repair(self, /, version="2026.1"):
                        async_create_issue(breaks_in_ha_version=version)

                    def setup(self):
                        self.create_repair("2027.1")
            """,
        },
    )
    result = find.scan(tmp_path, (2026, 1))
    assert result["deprecations"] == []


def test_scan_same_function_name(tmp_path: Path) -> None:
    """Test calls are not resolved when a function name is defined twice."""
    result = find.scan(write_repo(tmp_path, SAME_FUNCTION_NAME_FILES), (2099, 1))
    assert result["deprecations"] == []
    assert [(item["line"], item["source"]) for item in result["passthrough"]] == [
        (3, "version"),
        (10, "version"),
    ]


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
    ("name", "version", "suffix", "expected"),
    [
        pytest.param(
            "tplink",
            "2025.4",
            None,
            "deprecation-cleanup/tplink-2025.4",
            id="integration",
        ),
        pytest.param(
            "helpers/device_registry.py",
            "2025.12",
            None,
            "deprecation-cleanup/helpers-device_registry-2025.12",
            id="core-module",
        ),
        pytest.param(
            "const.py",
            "2026.10",
            None,
            "deprecation-cleanup/const-2026.10",
            id="top-level-module",
        ),
        pytest.param(
            "bayesian",
            "2022.10",
            "no_prob_given_false",
            "deprecation-cleanup/bayesian-2022.10-no_prob_given_false",
            id="issue-suffix",
        ),
        pytest.param(
            "eta",
            "2026.1",
            "Deprecated/Option.X",
            "deprecation-cleanup/eta-2026.1-deprecated-option-x",
            id="suffix-slug",
        ),
    ],
)
def test_branch_name(
    name: str, version: str, suffix: str | None, expected: str
) -> None:
    """Test cleanup branch names."""
    assert find.branch_name(name, version, suffix) == expected


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

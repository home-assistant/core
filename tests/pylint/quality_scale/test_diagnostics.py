"""Tests for the diagnostics quality scale checker."""

from pathlib import Path

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.quality_scale.diagnostics import DiagnosticsChecker
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
import pytest
import yaml

from tests.pylint import assert_adds_messages, assert_no_messages


@pytest.fixture(name="diagnostics_checker")
def diagnostics_checker_fixture(linter: UnittestLinter) -> DiagnosticsChecker:
    """Fixture to provide a diagnostics checker."""
    clear_quality_scale_cache()
    return DiagnosticsChecker(linter)


def _create_quality_scale(integration_dir: Path, rules: dict | None = None) -> None:
    """Create a quality_scale.yaml in the integration directory."""
    if rules is not None:
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump({"rules": rules}))


def _make_integration(tmp_path: Path) -> Path:
    """Create a fake integration directory under components/."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    return integration_dir


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def async_get_config_entry_diagnostics(hass, entry):
    return {"key": "value"}
""",
            id="config_entry_diagnostics",
        ),
        pytest.param(
            """
async def async_get_device_diagnostics(hass, entry, device):
    return {"key": "value"}
""",
            id="device_diagnostics",
        ),
        pytest.param(
            """
async def async_get_config_entry_diagnostics(hass, entry):
    return {"key": "value"}

async def async_get_device_diagnostics(hass, entry, device):
    return {"key": "value"}
""",
            id="both_diagnostics",
        ),
    ],
)
def test_diagnostics_present(
    linter: UnittestLinter,
    diagnostics_checker: DiagnosticsChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """No warning when diagnostics function is defined and rule is done."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"diagnostics": "done"})

    root_node = astroid.parse(code, "homeassistant.components.test_int.diagnostics")
    root_node.file = str(integration_dir / "diagnostics.py")

    walker = ASTWalker(linter)
    walker.add_checker(diagnostics_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_diagnostics_missing_fires(
    linter: UnittestLinter,
    diagnostics_checker: DiagnosticsChecker,
    tmp_path: Path,
) -> None:
    """Warning when no diagnostics function is defined and rule is done."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"diagnostics": "done"})

    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    pass
""",
        "homeassistant.components.test_int.diagnostics",
    )
    root_node.file = str(integration_dir / "diagnostics.py")

    walker = ASTWalker(linter)
    walker.add_checker(diagnostics_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-missing-diagnostics",
            node=root_node,
            line=0,
            col_offset=0,
        ),
    ):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("module_name", "rules"),
    [
        pytest.param(
            "homeassistant.components.test_int.diagnostics",
            None,
            id="no_quality_scale_file",
        ),
        pytest.param(
            "homeassistant.components.test_int.diagnostics",
            {"diagnostics": "todo"},
            id="rule_todo",
        ),
        pytest.param(
            "homeassistant.components.test_int.diagnostics",
            {"diagnostics": {"status": "exempt", "comment": "reason"}},
            id="rule_exempt",
        ),
        pytest.param(
            "homeassistant.components.test_int.sensor",
            {"diagnostics": "done"},
            id="not_diagnostics_module",
        ),
        pytest.param(
            "not_homeassistant.something.diagnostics",
            {"diagnostics": "done"},
            id="not_an_integration",
        ),
    ],
)
def test_diagnostics_not_fired(
    linter: UnittestLinter,
    diagnostics_checker: DiagnosticsChecker,
    tmp_path: Path,
    module_name: str,
    rules: dict | None,
) -> None:
    """No warning when rule is not done or module is not diagnostics."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, rules)

    root_node = astroid.parse(
        """
async def async_setup(hass, config):
    pass
""",
        module_name,
    )
    root_node.file = str(integration_dir / "diagnostics.py")

    walker = ASTWalker(linter)
    walker.add_checker(diagnostics_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)

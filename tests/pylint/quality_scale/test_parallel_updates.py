"""Tests for the parallel_updates quality scale checker."""

from pathlib import Path

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.quality_scale.parallel_updates import (
    ParallelUpdatesChecker,
)
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
import pytest
import yaml

from tests.pylint import assert_adds_messages, assert_no_messages


@pytest.fixture(name="parallel_updates_checker")
def parallel_updates_checker_fixture(linter: UnittestLinter) -> ParallelUpdatesChecker:
    """Fixture to provide a parallel updates checker."""
    clear_quality_scale_cache()
    return ParallelUpdatesChecker(linter)


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
    "module_name",
    [
        pytest.param(
            "homeassistant.components.test_int.sensor",
            id="sensor_platform",
        ),
        pytest.param(
            "homeassistant.components.test_int.light",
            id="light_platform",
        ),
    ],
)
def test_parallel_updates_present(
    linter: UnittestLinter,
    parallel_updates_checker: ParallelUpdatesChecker,
    tmp_path: Path,
    module_name: str,
) -> None:
    """No warning when PARALLEL_UPDATES is defined and rule is done."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"parallel-updates": "done"})

    root_node = astroid.parse("PARALLEL_UPDATES = 1\n", module_name)
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(parallel_updates_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_parallel_updates_zero(
    linter: UnittestLinter,
    parallel_updates_checker: ParallelUpdatesChecker,
    tmp_path: Path,
) -> None:
    """PARALLEL_UPDATES = 0 is accepted."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"parallel-updates": "done"})

    root_node = astroid.parse(
        "PARALLEL_UPDATES = 0\n", "homeassistant.components.test_int.sensor"
    )
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(parallel_updates_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_parallel_updates_annotated_assignment(
    linter: UnittestLinter,
    parallel_updates_checker: ParallelUpdatesChecker,
    tmp_path: Path,
) -> None:
    """PARALLEL_UPDATES: Final = 0 (annotated assignment) is accepted."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"parallel-updates": "done"})

    root_node = astroid.parse(
        "PARALLEL_UPDATES: Final = 0\n",
        "homeassistant.components.test_int.sensor",
    )
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(parallel_updates_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_parallel_updates_missing_fires(
    linter: UnittestLinter,
    parallel_updates_checker: ParallelUpdatesChecker,
    tmp_path: Path,
) -> None:
    """Warning when PARALLEL_UPDATES is missing and rule is done."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"parallel-updates": "done"})

    root_node = astroid.parse(
        "async def async_setup_entry(hass, entry, async_add_entities): pass\n",
        "homeassistant.components.test_int.sensor",
    )
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(parallel_updates_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-missing-parallel-updates",
            node=root_node,
            line=0,
            col_offset=0,
        ),
    ):
        walker.walk(root_node)


def test_parallel_updates_missing_status_done_dict(
    linter: UnittestLinter,
    parallel_updates_checker: ParallelUpdatesChecker,
    tmp_path: Path,
) -> None:
    """Warning fires for {status: done} dict form too."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(
        integration_dir,
        {"parallel-updates": {"status": "done", "comment": "set to 1"}},
    )

    root_node = astroid.parse(
        "async def async_setup_entry(hass, entry, async_add_entities): pass\n",
        "homeassistant.components.test_int.sensor",
    )
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(parallel_updates_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-missing-parallel-updates",
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
            "homeassistant.components.test_int.sensor",
            None,
            id="no_quality_scale_file",
        ),
        pytest.param(
            "homeassistant.components.test_int.sensor",
            {"parallel-updates": "todo"},
            id="rule_todo",
        ),
        pytest.param(
            "homeassistant.components.test_int.sensor",
            {"parallel-updates": {"status": "exempt", "comment": "reason"}},
            id="rule_exempt",
        ),
        pytest.param(
            "homeassistant.components.test_int.sensor",
            {"some-other-rule": "done"},
            id="rule_absent",
        ),
        pytest.param(
            "homeassistant.components.test_int.config_flow",
            {"parallel-updates": "done"},
            id="not_a_platform_module",
        ),
        pytest.param(
            "homeassistant.components.test_int",
            {"parallel-updates": "done"},
            id="init_module",
        ),
        pytest.param(
            "not_homeassistant.something.sensor",
            {"parallel-updates": "done"},
            id="not_an_integration",
        ),
    ],
)
def test_parallel_updates_not_fired(
    linter: UnittestLinter,
    parallel_updates_checker: ParallelUpdatesChecker,
    tmp_path: Path,
    module_name: str,
    rules: dict | None,
) -> None:
    """No warning when rule is not done, module is not a platform, etc."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, rules)

    root_node = astroid.parse(
        "async def async_setup_entry(hass, entry, async_add_entities): pass\n",
        module_name,
    )
    root_node.file = str(integration_dir / "sensor.py")

    walker = ASTWalker(linter)
    walker.add_checker(parallel_updates_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)

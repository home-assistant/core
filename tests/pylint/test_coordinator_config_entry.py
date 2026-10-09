"""Tests for the coordinator config entry checker."""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.coordinator_config_entry import (
    CoordinatorConfigEntryChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages

# Pre-load so astroid can resolve DataUpdateCoordinator in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")

_TYPED_ALIAS = """
from homeassistant.config_entries import ConfigEntry

type MyConfigEntry = ConfigEntry[MyCoordinator]
"""


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> CoordinatorConfigEntryChecker:
    """Fixture to provide a coordinator config entry checker."""
    return CoordinatorConfigEntryChecker(linter)


def _parse_coordinator(
    tmp_path: Path, code: str, init_code: str | None = _TYPED_ALIAS
) -> nodes.Module:
    """Create a fake integration and parse *code* as its coordinator module."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    if init_code is not None:
        (integration_dir / "__init__.py").write_text(init_code)

    root_node = astroid.parse(code, "homeassistant.components.test_int.coordinator")
    root_node.file = str(integration_dir / "coordinator.py")
    return root_node


def _walk(
    linter: UnittestLinter, checker: CoordinatorConfigEntryChecker, root: nodes.Module
) -> None:
    walker = ASTWalker(linter)
    walker.add_checker(checker)
    walker.walk(root)


@pytest.mark.parametrize(
    ("code", "init_code"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict]):
    config_entry: MyConfigEntry

    def __init__(self, hass, config_entry: MyConfigEntry) -> None:
        super().__init__(hass, LOGGER, config_entry=config_entry, name="test")
""",
            _TYPED_ALIAS,
            id="typed",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry: ConfigEntry) -> None:
        super().__init__(hass, LOGGER, config_entry=config_entry, name="test")
""",
            None,
            id="no_typed_config_entry_defined",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

class MyClient:
    config_entry: ConfigEntry

    def __init__(self, hass, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry
""",
            _TYPED_ALIAS,
            id="not_a_coordinator",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry: MyConfigEntry) -> None:
        super().__init__(hass, LOGGER, name="test")
        self.config_entry = config_entry
""",
            _TYPED_ALIAS,
            id="config_entry_not_passed_to_super",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: CoordinatorConfigEntryChecker,
    tmp_path: Path,
    code: str,
    init_code: str | None,
) -> None:
    """Test cases that should not trigger a warning."""
    root = _parse_coordinator(tmp_path, code, init_code)

    with assert_no_messages(linter):
        _walk(linter, checker, root)


@pytest.mark.parametrize(
    ("code", "init_code", "expected_args"),
    [
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry: ConfigEntry) -> None:
        super().__init__(hass, LOGGER, config_entry=config_entry, name="test")
""",
            _TYPED_ALIAS,
            ("`MyConfigEntry`",),
            id="argument",
        ),
        pytest.param(
            """
from homeassistant import config_entries
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, *, config_entry: config_entries.ConfigEntry | None):
        super().__init__(hass, LOGGER, config_entry=config_entry, name="test")
""",
            _TYPED_ALIAS,
            ("`MyConfigEntry`",),
            id="keyword_only_optional_attribute",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, entry: ConfigEntry) -> None:
        super().__init__(hass, LOGGER, config_entry=entry, name="test")
""",
            _TYPED_ALIAS,
            ("`MyConfigEntry`",),
            id="argument_with_other_name",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator):
    config_entry: ConfigEntry
""",
            _TYPED_ALIAS,
            ("`MyConfigEntry`",),
            id="class_annotation",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry: ConfigEntry) -> None:
        super().__init__(hass, LOGGER, config_entry=config_entry, name="test")
""",
            """
from homeassistant.config_entries import ConfigEntry

MyConfigEntry = ConfigEntry["MyCoordinator"]
""",
            ("`MyConfigEntry`",),
            id="assigned_alias",
        ),
    ],
)
def test_untyped_config_entry(
    linter: UnittestLinter,
    checker: CoordinatorConfigEntryChecker,
    tmp_path: Path,
    code: str,
    init_code: str,
    expected_args: tuple[str],
) -> None:
    """Test a plain ConfigEntry is flagged when a typed one exists."""
    root = _parse_coordinator(tmp_path, code, init_code)
    _walk(linter, checker, root)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-coordinator-untyped-config-entry"
    assert messages[0].args == expected_args


def test_redundant_config_entry(
    linter: UnittestLinter,
    checker: CoordinatorConfigEntryChecker,
    tmp_path: Path,
) -> None:
    """Test assigning self.config_entry after passing it to super is flagged."""
    root = _parse_coordinator(
        tmp_path,
        """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry: MyConfigEntry) -> None:
        super().__init__(hass, LOGGER, config_entry=config_entry, name="test")
        self.config_entry = config_entry
""",
    )
    assign = next(root.nodes_of_class(nodes.AssignAttr)).parent

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-coordinator-redundant-config-entry",
            node=assign,
            line=assign.lineno,
            col_offset=assign.col_offset,
            end_line=assign.end_lineno,
            end_col_offset=assign.end_col_offset,
        ),
    ):
        _walk(linter, checker, root)

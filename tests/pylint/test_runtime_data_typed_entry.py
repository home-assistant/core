"""Tests for the runtime_data typed config entry checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.runtime_data_typed_entry import (
    RuntimeDataTypedEntryChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

MODULE = "homeassistant.components.test_int"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> RuntimeDataTypedEntryChecker:
    """Fixture to provide a runtime_data typed config entry checker."""
    return RuntimeDataTypedEntryChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def async_setup_entry(hass, entry: MyConfigEntry):
    entry.runtime_data = MyData()
""",
            MODULE,
            id="typed_entry",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    coordinator = entry.runtime_data
""",
            MODULE,
            id="read_only",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry):
    entry.runtime_data = MyData()
""",
            MODULE,
            id="unannotated",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry: ConfigEntry):
    entry.runtime_data = MyData()
""",
            "homeassistant.helpers.something",
            id="outside_integration",
        ),
        pytest.param(
            """
def helper(entry: ConfigEntry, other: MyConfigEntry) -> None:
    other.runtime_data = MyData()
""",
            MODULE,
            id="other_argument_typed",
        ),
        pytest.param(
            """
def helper(entry: ConfigEntry) -> None:
    entry.runtime_data: MyData
""",
            MODULE,
            id="annotation_only",
        ),
        pytest.param(
            """
def helper(entry: MyConfigEntry) -> None:
    def inner() -> None:
        entry: ConfigEntry = get_entry()

    entry.runtime_data = MyData()
""",
            MODULE,
            id="untyped_declaration_in_nested_scope",
        ),
    ],
)
def test_no_message(
    linter: UnittestLinter,
    checker: RuntimeDataTypedEntryChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not add a message."""
    root = astroid.parse(code, module_name)
    with assert_no_messages(linter):
        walk_checker(linter, checker, root)


def _annotations(root: nodes.Module) -> list[nodes.NodeNG]:
    """Return every annotation in *root* that mentions ``ConfigEntry``."""
    annotations: list[nodes.NodeNG] = [
        node.annotation for node in root.nodes_of_class(nodes.AnnAssign)
    ]
    for arguments in root.nodes_of_class(nodes.Arguments):
        annotations.extend(
            annotation
            for annotation in (
                *arguments.annotations,
                *arguments.kwonlyargs_annotations,
            )
            if annotation is not None
        )
    return [node for node in annotations if "ConfigEntry" in node.as_string()]


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def async_setup_entry(hass, entry: ConfigEntry):
    entry.runtime_data = MyData()
""",
            id="argument",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry: ConfigEntry):
    if hass.data:
        entry.runtime_data = MyData()
    else:
        entry.runtime_data = OtherData()
""",
            id="set_twice_reported_once",
        ),
        pytest.param(
            """
def helper(*, entry: config_entries.ConfigEntry) -> None:
    entry.runtime_data = MyData()
""",
            id="keyword_only_qualified",
        ),
        pytest.param(
            """
def helper(hass) -> None:
    entry: ConfigEntry | None = hass.config_entries.async_get_entry("abc")
    entry.runtime_data = MyData()
""",
            id="annotated_local",
        ),
        pytest.param(
            """
def helper(hass) -> None:
    entry: ConfigEntry
    entry = hass.config_entries.async_get_entry("abc")
    entry.runtime_data = MyData()
""",
            id="declared_local_assigned_later",
        ),
        pytest.param(
            """
def helper(hass, entry: ConfigEntry) -> None:
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    entry.runtime_data = MyData()
""",
            id="reassigned_argument",
        ),
    ],
)
def test_untyped_config_entry(
    linter: UnittestLinter,
    checker: RuntimeDataTypedEntryChecker,
    code: str,
) -> None:
    """Test the annotation is flagged once when runtime_data is set."""
    root = astroid.parse(code, MODULE)
    (annotation,) = _annotations(root)
    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-runtime-data-untyped-config-entry",
            node=annotation,
            args=("entry",),
            line=annotation.lineno,
            col_offset=annotation.col_offset,
            end_line=annotation.end_lineno,
            end_col_offset=annotation.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)

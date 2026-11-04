"""Tests for the typed config entry checker."""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.typed_config_entry import (
    HassTypedConfigEntryChecker,
)
import pytest

from . import assert_no_messages, walk_checker

_TYPED_ALIAS = """
from homeassistant.config_entries import ConfigEntry

type MyConfigEntry = ConfigEntry[MyData]
"""


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> HassTypedConfigEntryChecker:
    """Fixture to provide a typed config entry checker."""
    return HassTypedConfigEntryChecker(linter)


def _parse(
    tmp_path: Path,
    code: str,
    init_code: str | None = _TYPED_ALIAS,
    module: str = "homeassistant.components.test_int.sensor",
) -> nodes.Module:
    """Create a fake integration and parse *code* as one of its modules."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    if init_code is not None:
        (integration_dir / "__init__.py").write_text(init_code)

    root_node = astroid.parse(code, module)
    root_node.file = str(integration_dir / f"{module.rsplit('.', 1)[-1]}.py")
    return root_node


@pytest.mark.parametrize(
    ("code", "init_code", "module"),
    [
        pytest.param(
            """
async def async_setup_entry(hass, entry: MyConfigEntry, add_entities) -> None:
    pass
""",
            _TYPED_ALIAS,
            "homeassistant.components.test_int.sensor",
            id="typed",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

async def async_setup_entry(hass, entry: ConfigEntry, add_entities) -> None:
    pass
""",
            None,
            "homeassistant.components.test_int.sensor",
            id="no_typed_config_entry_defined",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

type OtherConfigEntry = ConfigEntry[OtherData]
""",
            _TYPED_ALIAS,
            "homeassistant.components.test_int.sensor",
            id="alias_definition",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

async def test_something(entry: ConfigEntry) -> None:
    pass
""",
            _TYPED_ALIAS,
            "tests.components.test_int.test_sensor",
            id="test_module",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

class MyConfigFlow:
    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        pass
""",
            _TYPED_ALIAS,
            "homeassistant.components.test_int.config_flow",
            id="config_flow_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: HassTypedConfigEntryChecker,
    tmp_path: Path,
    code: str,
    init_code: str | None,
    module: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root = _parse(tmp_path, code, init_code, module)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root)


@pytest.mark.parametrize(
    ("code", "expected_lines"),
    [
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

async def async_setup_entry(hass, entry: ConfigEntry, add_entities) -> None:
    pass
""",
            [4],
            id="argument",
        ),
        pytest.param(
            """
from homeassistant import config_entries

async def async_unload_entry(
    hass, entry: config_entries.ConfigEntry
) -> bool:
    pass
""",
            [5],
            id="attribute_reference",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

def get_entry(hass, *, entry_id: str) -> ConfigEntry | None:
    pass
""",
            [4],
            id="optional_return",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

def get_entries(hass) -> list[ConfigEntry]:
    pass
""",
            [4],
            id="nested_in_generic",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

class MyEntity:
    _entry: ConfigEntry

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry: ConfigEntry = entry
""",
            [5, 7, 8],
            id="class_attribute_and_init",
        ),
        pytest.param(
            """
from homeassistant.config_entries import ConfigEntry

def handle(*entries: ConfigEntry, **by_id: ConfigEntry) -> None:
    pass
""",
            [4, 4],
            id="varargs",
        ),
    ],
)
def test_plain_config_entry(
    linter: UnittestLinter,
    checker: HassTypedConfigEntryChecker,
    tmp_path: Path,
    code: str,
    expected_lines: list[int],
) -> None:
    """Test a plain ConfigEntry is flagged when a typed one exists."""
    root = _parse(tmp_path, code)
    walk_checker(linter, checker, root)

    messages = linter.release_messages()
    assert [message.msg_id for message in messages] == [
        "home-assistant-use-typed-config-entry"
    ] * len(expected_lines)
    assert sorted(message.line for message in messages) == expected_lines
    assert {message.args for message in messages} == {("`MyConfigEntry`",)}

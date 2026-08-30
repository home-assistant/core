"""Checker for JSON-parsing a fixture instead of using the JSON fixture helpers."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

# JSON-parsing helpers imported as bare names (from homeassistant.util.json).
_JSON_PARSE_NAMES = frozenset(
    {
        "json_loads",
        "json_loads_array",
        "json_loads_object",
    }
)

# Attribute-form JSON parsers, only when called on the ``json`` module.
_JSON_PARSE_ATTRS = frozenset({"loads", "load"})

# Fixture loaders whose result is a raw string/bytes.
_FIXTURE_LOADER_NAMES = frozenset(
    {
        "load_fixture",
        "load_fixture_bytes",
        "async_load_fixture",
    }
)


def _is_json_parse_call(node: nodes.Call) -> bool:
    """Return True if the call parses JSON."""
    func = node.func
    if isinstance(func, nodes.Attribute):
        return (
            func.attrname in _JSON_PARSE_ATTRS
            and isinstance(func.expr, nodes.Name)
            and func.expr.name == "json"
        )
    if isinstance(func, nodes.Name):
        return func.name in _JSON_PARSE_NAMES
    return False


def _is_fixture_loader(node: nodes.NodeNG) -> bool:
    """Return True if the node is a call to a fixture loader."""
    if isinstance(node, nodes.Await):
        node = node.value
    if not isinstance(node, nodes.Call):
        return False
    func = node.func
    if isinstance(func, nodes.Attribute):
        return func.attrname in _FIXTURE_LOADER_NAMES
    if isinstance(func, nodes.Name):
        return func.name in _FIXTURE_LOADER_NAMES
    return False


class HassJsonFixtureChecker(BaseChecker):
    """Checker for JSON-parsing a loaded fixture."""

    name = "home_assistant_json_fixture"
    priority = -1
    msgs = {
        "W7435": (
            "Use a JSON fixture helper (e.g. load_json_object_fixture) instead of "
            "parsing a loaded fixture",
            "home-assistant-json-fixture",
            "Used when a fixture is loaded and then parsed as JSON instead of using "
            "the dedicated JSON fixture helpers",
        ),
    }
    options = ()

    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Visit a module definition."""
        # ``tests.common`` defines the JSON fixture helpers themselves, which
        # legitimately parse a loaded fixture.
        self._in_test_module = is_test_module(node.name) and node.name != "tests.common"

    def visit_call(self, node: nodes.Call) -> None:
        """Check for JSON parsing of a loaded fixture."""
        if (
            not self._in_test_module
            or not _is_json_parse_call(node)
            or not node.args
            or not _is_fixture_loader(node.args[0])
        ):
            return

        self.add_message("home-assistant-json-fixture", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassJsonFixtureChecker(linter))

"""Plugin to check decorators."""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassDecoratorChecker(BaseChecker):
    """Checker for decorators."""

    name = "hass_decorator"
    priority = -1
    msgs = {
        "W7471": (
            "A coroutine function should not be decorated with @callback",
            "hass-async-callback-decorator",
            "Used when a coroutine function has an invalid @callback decorator",
        ),
        "W7472": (
            "Fixture %s is invalid here, please %s",
            "hass-pytest-fixture-decorator",
            "Used when a pytest fixture is invalid",
        ),
    }

    def _get_pytest_fixture_node(self, node: nodes.FunctionDef) -> nodes.Call | None:
        for decorator in node.decorators.nodes:
            if (
                isinstance(decorator, nodes.Call)
                and decorator.func.as_string() == "pytest.fixture"
            ):
                return decorator

        return None

    def _get_pytest_fixture_node_keyword(
        self, decorator: nodes.Call, search_arg: str
    ) -> nodes.Keyword | None:
        for keyword in decorator.keywords:
            if keyword.arg == search_arg:
                return keyword

        return None

    def _check_pytest_fixture(
        self, node: nodes.FunctionDef, decoratornames: set[str]
    ) -> None:
        if (
            "_pytest.fixtures.FixtureFunctionMarker" not in decoratornames
            or not (root_name := node.root().name).startswith("tests.")
            or (decorator := self._get_pytest_fixture_node(node)) is None
            or not (
                scope_keyword := self._get_pytest_fixture_node_keyword(
                    decorator, "scope"
                )
            )
            or not isinstance(scope_keyword.value, nodes.Const)
            or not (scope := scope_keyword.value.value)
        ):
            return

        parts = root_name.split(".")
        test_component: str | None = None
        if root_name.startswith("tests.components.") and parts[2] != "conftest":
            test_component = parts[2]

        if scope == "session":
            if test_component:
                self.add_message(
                    "hass-pytest-fixture-decorator",
                    node=decorator,
                    args=("scope `session`", "use `package` or lower"),
                )
                return
            if not (
                autouse_keyword := self._get_pytest_fixture_node_keyword(
                    decorator, "autouse"
                )
            ) or (
                isinstance(autouse_keyword.value, nodes.Const)
                and not autouse_keyword.value.value
            ):
                self.add_message(
                    "hass-pytest-fixture-decorator",
                    node=decorator,
                    args=(
                        "scope/autouse combination",
                        "set `autouse=True` or reduce scope",
                    ),
                )
            return

        test_module = parts[3] if len(parts) > 3 else ""

        if test_component and scope == "package" and test_module != "conftest":
            self.add_message(
                "hass-pytest-fixture-decorator",
                node=decorator,
                args=("scope `package`", "use `module` or lower"),
            )

    def visit_asyncfunctiondef(self, node: nodes.AsyncFunctionDef) -> None:
        """Apply checks on an AsyncFunctionDef node."""
        if decoratornames := node.decoratornames():
            if "homeassistant.core.callback" in decoratornames:
                self.add_message("hass-async-callback-decorator", node=node)
            self._check_pytest_fixture(node, decoratornames)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Apply checks on an AsyncFunctionDef node."""
        if decoratornames := node.decoratornames():
            self._check_pytest_fixture(node, decoratornames)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassDecoratorChecker(linter))

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
            "Fixture %s is invalid here, please use %s",
            "hass-pytest-fixture-decorator",
            "Used when a pytest fixture is invalid",
        ),
    }

    def _get_pytest_fixture_node(self, node: nodes.FunctionDef) -> nodes.Call | None:
        for decorator in node.decorators.nodes:
            if not isinstance(decorator, nodes.Call):
                pass
            if decorator.func.as_string() == "pytest.fixture":
                return decorator

        return None

    def _check_pytest_fixture(
        self, node: nodes.FunctionDef, decoratornames: set[str]
    ) -> None:
        if (
            "_pytest.fixtures.FixtureFunctionMarker" not in decoratornames
            or (root_name := node.root().name) == "tests.components.conftest"
            or not root_name.startswith("tests.components.")
            or (decorator := self._get_pytest_fixture_node(node)) is None
        ):
            return

        for keyword in decorator.keywords:
            if (
                keyword.arg == "scope"
                and isinstance(keyword.value, nodes.Const)
                and keyword.value.value == "session"
            ):
                self.add_message(
                    "hass-pytest-fixture-decorator",
                    node=decorator,
                    args=(f"scope `{keyword.value.value}`", "`package` or lower"),
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

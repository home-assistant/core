"""Checker for decorator validation."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.ast_utils import extended_ancestors
from pylint_home_assistant.helpers.module_info import is_integration_module

_CALLBACK = "homeassistant.core.callback"
_COORDINATOR_WEATHER_ENTITY = (
    "homeassistant.components.weather.entity.CoordinatorWeatherEntity"
)
_CALLBACK_HOOKS: dict[str, str] = {
    "_handle_coordinator_update": (
        "homeassistant.helpers.update_coordinator.BaseCoordinatorEntity"
    ),
    "_async_write_ha_state": "homeassistant.helpers.entity.Entity",
    "_handle_processor_update": (
        "homeassistant.components.bluetooth.passive_update_processor"
        ".PassiveBluetoothProcessorEntity"
    ),
    "_async_forecast_daily": _COORDINATOR_WEATHER_ENTITY,
    "_async_forecast_hourly": _COORDINATOR_WEATHER_ENTITY,
    "_async_forecast_twice_daily": _COORDINATOR_WEATHER_ENTITY,
}


class HassDecoratorChecker(BaseChecker):
    """Checker for decorators."""

    name = "home_assistant_decorator"
    priority = -1
    msgs = {
        "W7402": (
            "A coroutine function should not be decorated with @callback",
            "home-assistant-async-callback-decorator",
            "Used when a coroutine function has an invalid @callback decorator",
        ),
        "W7403": (
            "Fixture %s is invalid here, please %s",
            "home-assistant-pytest-fixture-decorator",
            "Used when a pytest fixture is invalid",
        ),
        "W7463": (
            "%s overrides a @callback method of %s and should be decorated with "
            "@callback",
            "home-assistant-callback-override-missing-decorator",
            "Used when a sync method overrides a Home Assistant @callback method "
            "without the @callback decorator",
        ),
    }
    options = ()

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
                    "home-assistant-pytest-fixture-decorator",
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
                    "home-assistant-pytest-fixture-decorator",
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
                "home-assistant-pytest-fixture-decorator",
                node=decorator,
                args=("scope `package`", "use `module` or lower"),
            )

    def _check_callback_override(
        self, node: nodes.FunctionDef, decoratornames: set[str]
    ) -> None:
        if (
            not isinstance(class_node := node.parent, nodes.ClassDef)
            or (base_qname := _CALLBACK_HOOKS.get(node.name)) is None
            or _CALLBACK in decoratornames
            or not is_integration_module(node.root().name)
            or not any(
                ancestor.qname() == base_qname
                for ancestor in extended_ancestors(class_node)
            )
        ):
            return
        self.add_message(
            "home-assistant-callback-override-missing-decorator",
            node=node,
            args=(node.name, base_qname.rpartition(".")[2]),
        )

    def visit_asyncfunctiondef(self, node: nodes.AsyncFunctionDef) -> None:
        """Apply checks on an AsyncFunctionDef node."""
        if decoratornames := node.decoratornames():
            if _CALLBACK in decoratornames:
                self.add_message("home-assistant-async-callback-decorator", node=node)
            self._check_pytest_fixture(node, decoratornames)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Apply checks on a FunctionDef node."""
        decoratornames = node.decoratornames()
        self._check_callback_override(node, decoratornames)
        if decoratornames:
            self._check_pytest_fixture(node, decoratornames)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassDecoratorChecker(linter))

"""Plugin for detecting direct coordinator instantiation in integration tests.

Coordinators should not be instantiated directly in tests. Instead, the
behavior of a coordinator should be exercised indirectly through the entities
it backs, the state machine, the device registry, and the entity registry.
When the coordinator works correctly, the entities reflect that, and the
inverse holds as well -- if the entities behave correctly, the coordinator
behaves correctly.

This checker flags any test module under ``tests/components/**/test_*.py``
that directly instantiates a class which (transitively) inherits from
``homeassistant.helpers.update_coordinator.DataUpdateCoordinator``.
"""

from __future__ import annotations

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

_COORDINATOR_BASE_QNAME = (
    "homeassistant.helpers.update_coordinator.DataUpdateCoordinator"
)

# Names of mock factories whose ``spec`` argument acts as a stand-in for the
# real class. Passing a coordinator as ``spec`` is just as much a sign that
# the test is exercising the coordinator directly as instantiating it.
_MOCK_SPEC_FACTORIES: frozenset[str] = frozenset(
    {
        "AsyncMock",
        "MagicMock",
        "Mock",
        "NonCallableMagicMock",
        "NonCallableMock",
        "create_autospec",
    }
)


class HassEnforceNoCoordinatorInstantiationInTestsChecker(BaseChecker):
    """Checker that flags direct coordinator instantiation inside tests."""

    name = "hass_enforce_no_coordinator_instantiation_in_tests"
    priority = -1
    msgs = {
        "W7461": (
            "Coordinator '%s' should not be instantiated directly in tests; "
            "test the coordinator's behavior indirectly through entities, the "
            "state machine, and registries",
            "hass-no-coordinator-instantiation-in-tests",
            "Used when a test under tests/components/ directly instantiates a "
            "DataUpdateCoordinator subclass. Coordinator behavior should be "
            "verified through the entities it backs rather than by exercising "
            "the coordinator instance directly.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check whether this call instantiates, specs, or patches a coordinator."""
        root_name = node.root().name
        if not _is_integration_test_module(root_name):
            return

        # Direct instantiation: ``FooCoordinator(...)``.
        inferred = _safe_infer(node.func)
        if isinstance(inferred, nodes.ClassDef) and _inherits_from_coordinator(
            inferred
        ):
            self.add_message(
                "hass-no-coordinator-instantiation-in-tests",
                node=node,
                args=(inferred.name,),
            )
            return

        callee = _callee_name(node.func)

        # Mock factory using a coordinator as its ``spec``:
        # ``AsyncMock(spec=FooCoordinator)`` /
        # ``create_autospec(FooCoordinator)``.
        if callee in _MOCK_SPEC_FACTORIES:
            spec_arg = _get_spec_argument(node)
            spec_inferred = _safe_infer(spec_arg) if spec_arg is not None else None
            if isinstance(spec_inferred, nodes.ClassDef) and _inherits_from_coordinator(
                spec_inferred
            ):
                self.add_message(
                    "hass-no-coordinator-instantiation-in-tests",
                    node=node,
                    args=(spec_inferred.name,),
                )
            return

        # ``patch("...FooCoordinator")`` / ``patch.object(module, "FooCoordinator")``.
        if not _is_patch_callee(node.func):
            return

        patched = _resolve_patch_target(node)
        if isinstance(patched, nodes.ClassDef) and _inherits_from_coordinator(patched):
            self.add_message(
                "hass-no-coordinator-instantiation-in-tests",
                node=node,
                args=(patched.name,),
            )


def _is_integration_test_module(root_name: str) -> bool:
    """Return True if ``root_name`` belongs to an integration test module."""
    if not root_name.startswith("tests.components."):
        return False
    parts = root_name.split(".")
    # Expect ``tests.components.<integration>.test_<name>[...]``
    return len(parts) >= 4 and parts[-1].startswith("test_")


def _safe_infer(node: nodes.NodeNG) -> nodes.NodeNG | None:
    """Best-effort inference that swallows astroid errors."""
    try:
        inferred = next(node.infer(), None)
    except astroid.InferenceError:
        return None
    if inferred is astroid.Uninferable:
        return None
    return inferred


def _callee_name(func: nodes.NodeNG) -> str | None:
    """Return the trailing name of the callable being invoked, if any."""
    match func:
        case nodes.Name(name=name) | nodes.Attribute(attrname=name):
            return name
        case _:
            return None


def _get_spec_argument(node: nodes.Call) -> nodes.NodeNG | None:
    """Return the value passed as ``spec`` to a Mock factory call."""
    for keyword in node.keywords or ():
        if keyword.arg == "spec":
            return keyword.value
    # ``create_autospec`` and Mock factories accept ``spec`` as the first
    # positional argument.
    if node.args:
        return node.args[0]
    return None


def _is_patch_callee(func: nodes.NodeNG) -> bool:
    """Return True if ``func`` looks like ``patch`` or ``patch.object``."""
    match func:
        case nodes.Name(name="patch"):
            return True
        case nodes.Attribute(attrname="object", expr=nodes.Name(name="patch")):
            return True
        case nodes.Attribute(attrname="patch"):
            # e.g. ``mock.patch(...)``.
            return True
        case nodes.Attribute(attrname="object", expr=nodes.Attribute(attrname="patch")):
            # e.g. ``mock.patch.object(...)``.
            return True
        case _:
            return False


def _resolve_patch_target(node: nodes.Call) -> nodes.NodeNG | None:
    """Resolve the object being replaced by a ``patch``/``patch.object`` call."""
    if not node.args:
        return None

    func = node.func
    is_object_form = isinstance(func, nodes.Attribute) and func.attrname == "object"

    if is_object_form:
        # ``patch.object(target_module, "attr", ...)``.
        if len(node.args) < 2:
            return None
        target_module = _safe_infer(node.args[0])
        attr_node = node.args[1]
        if not isinstance(attr_node, nodes.Const) or not isinstance(
            attr_node.value, str
        ):
            return None
        return _lookup_attribute(target_module, attr_node.value)

    # ``patch("a.b.c.Name", ...)``.
    target_node = node.args[0]
    if not isinstance(target_node, nodes.Const) or not isinstance(
        target_node.value, str
    ):
        return None
    return _resolve_dotted_path(target_node.value)


def _resolve_dotted_path(dotted: str) -> nodes.NodeNG | None:
    """Resolve ``a.b.c.Name`` into the underlying astroid node."""
    if "." not in dotted:
        return None
    module_path, _, attr = dotted.rpartition(".")
    try:
        module = astroid.MANAGER.ast_from_module_name(module_path)
    except astroid.AstroidImportError:
        return None
    return _lookup_attribute(module, attr)


def _lookup_attribute(container: nodes.NodeNG | None, attr: str) -> nodes.NodeNG | None:
    """Look ``attr`` up on a module or class node."""
    if container is None:
        return None
    try:
        matches = container.getattr(attr)
    except astroid.AttributeInferenceError, AttributeError:
        return None
    return matches[0] if matches else None


def _inherits_from_coordinator(class_def: nodes.ClassDef) -> bool:
    """Return True if ``class_def`` inherits from a coordinator base."""
    if class_def.qname() == _COORDINATOR_BASE_QNAME:
        return True
    try:
        ancestors = class_def.ancestors()
    except astroid.MroError:
        return False
    return any(ancestor.qname() == _COORDINATOR_BASE_QNAME for ancestor in ancestors)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceNoCoordinatorInstantiationInTestsChecker(linter))
